# Copyright (C) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#

import sys
import threading
import os
import time
from urllib2 import HTTPError
from oscpluginprjmake import utils
from oscpluginprjmake import settings
from osc import core
import subprocess
from multiprocessing import Lock, Process

def download_worker(dl_list, silent=False):
    for (apiurl, project, repo, arch, package, specfile, bifile) in dl_list:
        if not silent:
            print "Downloading %s" % bifile
        cmd = ['osc', '-A', apiurl, 'api']
        if specfile is not None:
            cmd += ['-X', 'POST', '-d', specfile]
        else:
            cmd += ['-X', 'GET']
        cmd += ['/build/%s/%s/%s/%s/_buildinfo' %
            (project, repo, arch, package)]

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        (out, err) = p.communicate()
        if p.returncode != 0:
            print("Download worker error: %s" % err)
            sys.exit(1)

        fd = open(bifile, 'w+')
        fd.write(out)
        fd.close()

    sys.exit(0)

# Split workload of size x evenly among n workers.
# Returns a list of (start, end) index tuples.
def split_jobs(job_amount, worker_amount):
    job_indexes = []
    if worker_amount == 0:
        return job_indexes

    payload_size = job_amount / worker_amount
    extra_jobs = job_amount % worker_amount
    start = 0
    end = payload_size + (1 if extra_jobs else 0)
    for i in range(worker_amount):
        job_indexes += [(start, end)]
        start += payload_size + (1 if extra_jobs > i else 0)
        end += payload_size + (1 if extra_jobs > i + 1 else 0)

    return job_indexes

# Class that finds locally stored build infos
# or downloads them from OBS server if needed.
class BuildInfoThread(threading.Thread):
    _stage = 0
    _interrupt = 0
    _disables = {}
    _error = None
    _sts = None
    _stage_progress = {}
    _stage_progress_updated = False
    _download_jobs = []

    def __init__(_self, sts):
        _self._sts = sts
        super(BuildInfoThread, _self).__init__()

    def update_progress(_self, stage, message):
        _self._stage_progress[stage] = message
        _self._stage_progress_updated = True

    def add_download_job(_self, bi_pkg, package, specfile, bifile):
        _self._download_jobs += [(_self._sts.get('apiurl'), package._project,
            _self._sts.get('repo'), _self._sts.get('arch'), package._name,
            specfile, bifile)]

    # Download missing buildinfo file using worker processes.
    def execute_downloads(_self):
        workers = []
        worker_amount = _self._sts.get('download-jobs')
        total_jobs = len(_self._download_jobs)
        silent = False if _self._stage == 0 else True
        job_indexes = split_jobs(total_jobs, worker_amount)
        for i in range(worker_amount):
            (start, end) = job_indexes[i]
            worker_payload = _self._download_jobs[start:end]
            workers += [Process(target=download_worker,
                args=(worker_payload, silent))]

        for w in workers:
            w.start()

        for w in workers:
            while w.is_alive():
                if _self._interrupt:
                    w.terminate()
                w.join(0.1)
            if w.exitcode != 0:
                _self._stage = -1
                _self._error = core.oscerr.OscIOError(
                    None, "Buildinfo download failed")
        _self._download_jobs = []

    # Try to find buildinfo locally or get it from server
    def find_bifile(_self, pkg):
        bidir = _self._sts.get('buildinfodir')
        if pkg._specfile is not None:
            specfile = utils.file_to_string(pkg._specfile)
            bi_pkg = '_repository'
            bifile = os.path.join(bidir, '%s.%s.bi' %
                (pkg, pkg._specfile_md5sum))
        else:
            specfile = None
            bi_pkg = pkg
            bifile = os.path.join(bidir, '%s.bi' % pkg)
        if not os.path.exists(bifile):
            if _self._sts.get('offline'):
                _self._stage = -1
                _self._error = core.oscerr.WrongArgs(
                    'Missing buildinfo for %s, --offline not possible' % pkg)
            _self.add_download_job(bi_pkg, pkg, specfile, bifile)

    # Try to find builddepinfo locally or get it from server
    def find_bdifile(_self, pkg):
        bidir = _self._sts.get('buildinfodir')
        bdifile = os.path.join(bidir, '%s.bdi' % pkg)
        if not os.path.exists(bdifile):
            if _self._sts.get('offline'):
                self._stage = -1
                self._error = core.oscerr.WrongArgs(
                    'Missing builddepinfo for %s, offline build not possible',
                    pkg)
            bdi_pkg = pkg
            try:
                dependson = core.get_dependson(_self._sts.get('apiurl'),
                    _self._sts.get('project'), _self._sts.get('repo'),
                    _self._sts.get('arch'), [pkg], False)
                fd = open(bdifile, 'w+')
                fd.write(dependson)
                fd.close()
            except HTTPError as e:
                self._stage = -1
                reason = utils.get_http_error_reason(e)
                self._error = core.oscerr.OscIOError(e,
                    'Failed to download builddepinfo for %s: %s'
                    % (pkg, e.reason))

    def set_disables(_self, pkg):
        if (_self._sts.get('disable_mode') != 'all'
            and pkg in _self._sts.get('pkgs_changed')):
            return
        if utils.get_package_state(
            _self._sts.get('projectdir'), pkg) == 'added':
            return
        enabled = utils.is_pkg_enabled(_self._sts, pkg)
        if not enabled:
            _self._disables[pkg] = 1

    def run(_self):
        _self._stage = 0
        mode = _self._sts.get('buildorder_calc_mode')
        pkgs = _self._sts.get('pkgs_changed')
        for pkg in pkgs:
            if _self._interrupt:
                _self._stage = -1
                _self._error = core.oscerr.UserAbort()
                return
            if mode == "buildinfo":
                _self.find_bifile(pkg)
            elif mode == "builddepinfo":
                _self.find_bdifile(pkg)
            else:
                _self._stage = -1
                _self._error = StandardError(
                    "Unknown buildorder calc mode: %s" % mode)
            if _self._stage == -1:
                return
            _self.set_disables(pkg)
        if len(_self._download_jobs) > 0:
            _self.execute_downloads()
        if _self._stage == -1:
            return
        _self._stage = 1
        pkgs = _self._sts.get('packages')
        for pkg in pkgs:
            if _self._interrupt:
                _self._stage = -1
                _self._error = core.oscerr.UserAbort()
                return
            if mode == "buildinfo":
                _self.find_bifile(pkg)
            elif mode == "builddepinfo":
                _self.find_bdifile(pkg)
            else:
                _self._stage = -1
                _self._error = StandardError(
                    "Unknown buildorder calc mode: %s" % mode)
            if _self._stage == -1:
                return
            _self.set_disables(pkg)
        if len(_self._download_jobs) > 0:
            _self.execute_downloads()
        if _self._stage == -1:
            return
        _self._stage = 2

    def wait_for_stage(_self, stage):
        while 1:
            if _self._stage >= stage:
                return 0
            elif _self._stage == -1:
                return 1
            if (_self._stage_progress_updated and
                _self._stage_progress.has_key(stage)):
                _self._stage_progress_updated = False
                print(_self._stage_progress[stage])
            time.sleep(0.1)

    def get_disables(_self):
        return _self._disables

    def interrupt(_self):
        _self._interrupt = 1

    def get_error(_self):
        return _self._error

# vim: et sw=4 ts=4
