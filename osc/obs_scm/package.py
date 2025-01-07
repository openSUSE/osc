import difflib
import fnmatch
import glob
import shutil
import os
import sys
import tempfile
from functools import total_ordering
from typing import Optional

from .. import conf
from .. import oscerr
from ..util.xml import ET
from ..util.xml import xml_fromstring
from ..util.xml import xml_parse
from .file import File
from .linkinfo import Linkinfo
from .serviceinfo import Serviceinfo
from .store import __store_version__
from .store import Store
from .store import check_store_version
from .store import read_inconflict
from .store import read_filemeta
from .store import read_sizelimit
from .store import read_tobeadded
from .store import read_tobedeleted
from .store import store
from .store import store_read_file
from .store import store_write_project
from .store import store_write_string


@total_ordering
class Package:
    """represent a package (its directory) and read/keep/write its metadata"""

    # should _meta be a required file?
    REQ_STOREFILES = ('_project', '_package', '_apiurl', '_files', '_osclib_version')
    OPT_STOREFILES = ('_to_be_added', '_to_be_deleted', '_in_conflict', '_in_update',
                      '_in_commit', '_meta', '_meta_mode', '_frozenlink', '_pulled', '_linkrepair',
                      '_size_limit', '_commit_msg', '_last_buildroot')

    def __init__(self, workingdir, progress_obj=None, size_limit=None, wc_check=True):
        from .. import store as osc_store

        global store

        self.todo = []
        if os.path.isfile(workingdir) or not os.path.exists(workingdir):
            # workingdir is a file
            # workingdir doesn't exist -> it points to a non-existing file in a working dir (e.g. during mv)
            workingdir, todo_entry = os.path.split(workingdir)
            self.todo.append(todo_entry)

        self.dir = workingdir or "."
        self.absdir = os.path.abspath(self.dir)
        self.store = osc_store.get_store(self.dir, check=wc_check)
        self.store.assert_is_package()
        self.storedir = os.path.join(self.absdir, store)
        self.progress_obj = progress_obj
        self.size_limit = size_limit
        self.scm_url = self.store.scmurl
        if size_limit and size_limit == 0:
            self.size_limit = None

        self.prjname = self.store.project
        self.name = self.store.package
        self.apiurl = self.store.apiurl

        self.update_datastructs()
        dirty_files = []
        if wc_check:
            dirty_files = self.wc_check()
        if dirty_files:
            msg = 'Your working copy \'%s\' is in an inconsistent state.\n' \
                'Please run \'osc repairwc %s\' (Note this might _remove_\n' \
                'files from the .osc/ dir). Please check the state\n' \
                'of the working copy afterwards (via \'osc status %s\')' % (self.dir, self.dir, self.dir)
            raise oscerr.WorkingCopyInconsistent(self.prjname, self.name, dirty_files, msg)

    def __repr__(self):
        return super().__repr__() + f"({self.prjname}/{self.name})"

    def __hash__(self):
        return hash((self.name, self.prjname, self.apiurl))

    def __eq__(self, other):
        return (self.name, self.prjname, self.apiurl) == (other.name, other.prjname, other.apiurl)

    def __lt__(self, other):
        return (self.name, self.prjname, self.apiurl) < (other.name, other.prjname, other.apiurl)

    @classmethod
    def from_paths(cls, paths, progress_obj=None, *, skip_dirs=False):
        """
        Return a list of Package objects from working copies in given paths.
        """
        packages = []
        for path in paths:
            if skip_dirs and os.path.isdir(path):
                continue

            package = cls(path, progress_obj)
            seen_package = None
            try:
                # re-use an existing package
                seen_package_index = packages.index(package)
                seen_package = packages[seen_package_index]
            except ValueError:
                pass

            if seen_package:
                # merge package into seen_package
                if seen_package.absdir != package.absdir:
                    raise oscerr.PackageExists(package.prjname, package.name, "Duplicate package")
                seen_package.merge(package)
            else:
                # use the new package instance
                packages.append(package)

        return packages

    @classmethod
    def from_paths_nofail(cls, paths, progress_obj=None, *, skip_dirs=False):
        """
        Return a list of Package objects from working copies in given paths
        and a list of strings with paths that do not contain Package working copies.
        """
        packages = []
        failed_to_load = []
        for path in paths:
            if skip_dirs and os.path.isdir(path):
                continue

            try:
                package = cls(path, progress_obj)
            except oscerr.NoWorkingCopy:
                failed_to_load.append(path)
                continue

            # the following code is identical to from_paths()
            seen_package = None
            try:
                # re-use an existing package
                seen_package_index = packages.index(package)
                seen_package = packages[seen_package_index]
            except ValueError:
                pass

            if seen_package:
                # merge package into seen_package
                if seen_package.absdir != package.absdir:
                    raise oscerr.PackageExists(package.prjname, package.name, "Duplicate package")
                seen_package.merge(package)
            else:
                # use the new package instance
                packages.append(package)

        return packages, failed_to_load

    def wc_check(self):
        dirty_files = []
        if self.scm_url:
            return dirty_files
        for fname in self.filenamelist:
            if not self.store.sources_is_file(fname) and fname not in self.skipped:
                dirty_files.append(fname)
        for fname in Package.REQ_STOREFILES:
            if not os.path.isfile(os.path.join(self.storedir, fname)):
                dirty_files.append(fname)
        for fname in self.store.sources_list_files():
            if fname in self.filenamelist and fname in self.skipped:
                dirty_files.append(fname)
            elif fname not in self.filenamelist:
                dirty_files.append(fname)
        for fname in self.to_be_deleted[:]:
            if fname not in self.filenamelist:
                dirty_files.append(fname)
        for fname in self.in_conflict[:]:
            if fname not in self.filenamelist:
                dirty_files.append(fname)
        return dirty_files

    def wc_repair(self, apiurl: Optional[str] = None) -> bool:
        from ..core import get_source_file

        repaired: bool = False

        store = Store(self.dir, check=False)
        store.assert_is_package()
        # check_store_version() does the metadata migration that was disabled due to Store(..., check=False)
        check_store_version(self.absdir)

        # there was a time when osc did not write _osclib_version file; let's assume these checkouts have version 1.0
        if not store.exists("_osclib_version"):
            store.write_string("_osclib_version", "1.0")

        if not store.exists("_apiurl") or apiurl:
            if apiurl is None:
                msg = 'cannot repair wc: the \'_apiurl\' file is missing but ' \
                    'no \'apiurl\' was passed to wc_repair'
                # hmm should we raise oscerr.WrongArgs?
                raise oscerr.WorkingCopyInconsistent(self.prjname, self.name, [], msg)
            # sanity check
            conf.parse_apisrv_url(None, apiurl)
            store.apiurl = apiurl
            self.apiurl = apiurl
            repaired = True

        # all files which are present in the filelist have to exist in the storedir
        for f in self.filelist:
            # XXX: should we also check the md5?
            if not self.store.sources_is_file(f.name) and f.name not in self.skipped:
                # if get_source_file fails we're screwed up...
                get_source_file(self.apiurl, self.prjname, self.name, f.name,
                                targetfilename=self.store.sources_get_path(f.name), revision=self.rev,
                                mtime=f.mtime)
                repaired = True

        for fname in store:
            if fname in Package.REQ_STOREFILES or fname in Package.OPT_STOREFILES or \
                    fname.startswith('_build'):
                continue

        for fname in self.store.sources_list_files():
            if fname not in self.filenamelist or fname in self.skipped:
                # this file does not belong to the storedir so remove it
                os.unlink(self.store.sources_get_path(fname))
                repaired = True

        for fname in self.to_be_deleted[:]:
            if fname not in self.filenamelist:
                self.to_be_deleted.remove(fname)
                self.write_deletelist()
                repaired = True

        for fname in self.in_conflict[:]:
            if fname not in self.filenamelist:
                self.in_conflict.remove(fname)
                self.write_conflictlist()
                repaired = True

        return repaired

    def info(self):
        from ..core import info_templ
        from ..core import makeurl

        source_url = makeurl(self.apiurl, ['source', self.prjname, self.name])
        r = info_templ % (self.prjname, self.name, self.absdir, self.apiurl, source_url, self.srcmd5, self.rev, self.linkinfo)
        return r

    def addfile(self, n):
        from ..core import statfrmt

        if not os.path.exists(os.path.join(self.absdir, n)):
            raise oscerr.OscIOError(None, f'error: file \'{n}\' does not exist')
        if n in self.to_be_deleted:
            self.to_be_deleted.remove(n)
            self.write_deletelist()
        elif n in self.filenamelist or n in self.to_be_added:
            raise oscerr.PackageFileConflict(self.prjname, self.name, n, f'osc: warning: \'{n}\' is already under version control')
        if self.dir != '.':
            pathname = os.path.join(self.dir, n)
        else:
            pathname = n
        self.to_be_added.append(n)
        self.write_addlist()
        print(statfrmt('A', pathname))

    def delete_file(self, n, force=False):
        """deletes a file if possible and marks the file as deleted"""
        state = '?'
        try:
            state = self.status(n)
        except OSError as ioe:
            if not force:
                raise ioe
        if state in ['?', 'A', 'M', 'R', 'C'] and not force:
            return (False, state)
        # special handling for skipped files: if file exists, simply delete it
        if state == 'S':
            exists = os.path.exists(os.path.join(self.dir, n))
            self.delete_localfile(n)
            return (exists, 'S')

        self.delete_localfile(n)
        was_added = n in self.to_be_added
        if state in ('A', 'R') or state == '!' and was_added:
            self.to_be_added.remove(n)
            self.write_addlist()
        elif state == 'C':
            # don't remove "merge files" (*.mine, *.new...)
            # that's why we don't use clear_from_conflictlist
            self.in_conflict.remove(n)
            self.write_conflictlist()
        if state not in ('A', '?') and not (state == '!' and was_added):
            self.put_on_deletelist(n)
            self.write_deletelist()
        return (True, state)

    def delete_localfile(self, n):
        try:
            os.unlink(os.path.join(self.dir, n))
        except:
            pass

    def put_on_deletelist(self, n):
        if n not in self.to_be_deleted:
            self.to_be_deleted.append(n)

    def put_on_conflictlist(self, n):
        if n not in self.in_conflict:
            self.in_conflict.append(n)

    def put_on_addlist(self, n):
        if n not in self.to_be_added:
            self.to_be_added.append(n)

    def clear_from_conflictlist(self, n):
        """delete an entry from the file, and remove the file if it would be empty"""
        if n in self.in_conflict:

            filename = os.path.join(self.dir, n)
            storefilename = self.store.sources_get_path(n)
            myfilename = os.path.join(self.dir, n + '.mine')
            upfilename = os.path.join(self.dir, n + '.new')

            try:
                os.unlink(myfilename)
                os.unlink(upfilename)
                if self.islinkrepair() or self.ispulled():
                    os.unlink(os.path.join(self.dir, n + '.old'))
            except:
                pass

            self.in_conflict.remove(n)

            self.write_conflictlist()

    # XXX: this isn't used at all
    def write_meta_mode(self):
        # XXX: the "elif" is somehow a contradiction (with current and the old implementation
        #      it's not possible to "leave" the metamode again) (except if you modify pac.meta
        #      which is really ugly:) )
        if self.meta:
            store_write_string(self.absdir, '_meta_mode', '')
        elif self.ismetamode():
            os.unlink(os.path.join(self.storedir, '_meta_mode'))

    def write_sizelimit(self):
        if self.size_limit and self.size_limit <= 0:
            try:
                os.unlink(os.path.join(self.storedir, '_size_limit'))
            except:
                pass
        else:
            store_write_string(self.absdir, '_size_limit', str(self.size_limit) + '\n')

    def write_addlist(self):
        self.__write_storelist('_to_be_added', self.to_be_added)

    def write_deletelist(self):
        self.__write_storelist('_to_be_deleted', self.to_be_deleted)

    def delete_source_file(self, n):
        """delete local a source file"""
        self.delete_localfile(n)
        self.store.sources_delete_file(n)

    def delete_remote_source_file(self, n):
        """delete a remote source file (e.g. from the server)"""
        from ..core import http_DELETE
        from ..core import makeurl

        query = {"rev": "upload"}
        u = makeurl(self.apiurl, ['source', self.prjname, self.name, n], query=query)
        http_DELETE(u)

    def put_source_file(self, n, tdir, copy_only=False):
        from ..core import http_PUT
        from ..core import makeurl

        query = {"rev": "repository"}
        tfilename = os.path.join(tdir, n)
        shutil.copyfile(os.path.join(self.dir, n), tfilename)
        # escaping '+' in the URL path (note: not in the URL query string) is
        # only a workaround for ruby on rails, which swallows it otherwise
        if not copy_only:
            u = makeurl(self.apiurl, ['source', self.prjname, self.name, n], query=query)
            http_PUT(u, file=tfilename)
        if n in self.to_be_added:
            self.to_be_added.remove(n)

    def __commit_update_store(self, tdir):
        """move files from transaction directory into the store"""
        for filename in os.listdir(tdir):
            os.rename(os.path.join(tdir, filename), self.store.sources_get_path(filename))

    def __generate_commitlist(self, todo_send):
        root = ET.Element('directory')
        for i in sorted(todo_send.keys()):
            ET.SubElement(root, 'entry', name=i, md5=todo_send[i])
        return root

    @staticmethod
    def commit_filelist(apiurl: str, project: str, package: str, filelist, msg="", user=None, **query):
        """send the commitlog and the local filelist to the server"""
        from ..core import ET_ENCODING
        from ..core import http_POST
        from ..core import makeurl

        if user is None:
            user = conf.get_apiurl_usr(apiurl)
        query.update({'cmd': 'commitfilelist', 'user': user, 'comment': msg})
        u = makeurl(apiurl, ['source', project, package], query=query)
        f = http_POST(u, data=ET.tostring(filelist, encoding=ET_ENCODING))
        root = xml_parse(f).getroot()
        return root

    @staticmethod
    def commit_get_missing(filelist):
        """returns list of missing files (filelist is the result of commit_filelist)"""
        from ..core import ET_ENCODING

        error = filelist.get('error')
        if error is None:
            return []
        elif error != 'missing':
            raise oscerr.APIError('commit_get_missing_files: '
                                  'unexpected \'error\' attr: \'%s\'' % error)
        todo = []
        for n in filelist.findall('entry'):
            name = n.get('name')
            if name is None:
                raise oscerr.APIError('missing \'name\' attribute:\n%s\n'
                                      % ET.tostring(filelist, encoding=ET_ENCODING))
            todo.append(n.get('name'))
        return todo

    def __send_commitlog(self, msg, local_filelist, validate=False):
        """send the commitlog and the local filelist to the server"""
        query = {}
        if self.islink() and self.isexpanded():
            query['keeplink'] = '1'
            if conf.config['linkcontrol'] or self.isfrozen():
                query['linkrev'] = self.linkinfo.srcmd5
            if self.ispulled():
                query['repairlink'] = '1'
                query['linkrev'] = self.get_pulled_srcmd5()
        if self.islinkrepair():
            query['repairlink'] = '1'
        if validate:
            query['withvalidate'] = '1'
        return self.commit_filelist(self.apiurl, self.prjname, self.name,
                                    local_filelist, msg, **query)

    def commit(self, msg='', verbose=False, skip_local_service_run=False, can_branch=False, force=False):
        from ..core import ET_ENCODING
        from ..core import branch_pkg
        from ..core import dgst
        from ..core import getTransActPath
        from ..core import http_GET
        from ..core import makeurl
        from ..core import print_request_list
        from ..core import sha256_dgst
        from ..core import statfrmt

        # commit only if the upstream revision is the same as the working copy's
        upstream_rev = self.latest_rev()
        if self.rev != upstream_rev:
            raise oscerr.WorkingCopyOutdated((self.absdir, self.rev, upstream_rev))

        if not skip_local_service_run:
            r = self.run_source_services(mode="trylocal", verbose=verbose)
            if r != 0:
                # FIXME: it is better to raise this in Serviceinfo.execute with more
                # information (like which service/command failed)
                raise oscerr.ServiceRuntimeError('A service failed with error: %d' % r)

        # check if it is a link, if so, branch the package
        if self.is_link_to_different_project():
            if can_branch:
                orgprj = self.get_local_origin_project()
                print(f"Branching {self.name} from {orgprj} to {self.prjname}")
                exists, targetprj, targetpkg, srcprj, srcpkg = branch_pkg(
                    self.apiurl, orgprj, self.name, target_project=self.prjname)
                # update _meta and _files to sychronize the local package
                # to the new branched one in OBS
                self.update_local_pacmeta()
                self.update_local_filesmeta()
            else:
                print(f"{self.name} Not commited because is link to a different project")
                return 1

        if not self.todo:
            self.todo = [i for i in self.to_be_added if i not in self.filenamelist] + self.filenamelist

        pathn = getTransActPath(self.dir)

        todo_send = {}
        todo_delete = []
        real_send = []
        sha256sums = {}
        for filename in self.filenamelist + [i for i in self.to_be_added if i not in self.filenamelist]:
            if filename.startswith('_service:') or filename.startswith('_service_'):
                continue
            st = self.status(filename)
            if st == 'C':
                print('Please resolve all conflicts before committing using "osc resolved FILE"!')
                return 1
            elif filename in self.todo:
                if st in ('A', 'R', 'M'):
                    todo_send[filename] = dgst(os.path.join(self.absdir, filename))
                    sha256sums[filename] = sha256_dgst(os.path.join(self.absdir, filename))
                    real_send.append(filename)
                    print(statfrmt('Sending', os.path.join(pathn, filename)))
                elif st in (' ', '!', 'S'):
                    if st == '!' and filename in self.to_be_added:
                        print(f'file \'{filename}\' is marked as \'A\' but does not exist')
                        return 1
                    f = self.findfilebyname(filename)
                    if f is None:
                        raise oscerr.PackageInternalError(self.prjname, self.name,
                                                          'error: file \'%s\' with state \'%s\' is not known by meta'
                                                          % (filename, st))
                    todo_send[filename] = f.md5
                elif st == 'D':
                    todo_delete.append(filename)
                    print(statfrmt('Deleting', os.path.join(pathn, filename)))
            elif st in ('R', 'M', 'D', ' ', '!', 'S'):
                # ignore missing new file (it's not part of the current commit)
                if st == '!' and filename in self.to_be_added:
                    continue
                f = self.findfilebyname(filename)
                if f is None:
                    raise oscerr.PackageInternalError(self.prjname, self.name,
                                                      'error: file \'%s\' with state \'%s\' is not known by meta'
                                                      % (filename, st))
                todo_send[filename] = f.md5
            if ((self.ispulled() or self.islinkrepair() or self.isfrozen())
                    and st != 'A' and filename not in sha256sums):
                # Ignore files with state 'A': if we should consider it,
                # it would have been in pac.todo, which implies that it is
                # in sha256sums.
                # The storefile is guaranteed to exist (since we have a
                # pulled/linkrepair wc, the file cannot have state 'S')
                storefile = self.store.sources_get_path(filename)
                sha256sums[filename] = sha256_dgst(storefile)

        if not force and not real_send and not todo_delete and not self.islinkrepair() and not self.ispulled():
            print(f'nothing to do for package {self.name}')
            return 1

        print('Transmitting file data', end=' ')
        filelist = self.__generate_commitlist(todo_send)
        sfilelist = self.__send_commitlog(msg, filelist, validate=True)
        hash_entries = [e for e in sfilelist.findall('entry') if e.get('hash') is not None]
        if sfilelist.get('error') and hash_entries:
            name2elem = {e.get('name'): e for e in filelist.findall('entry')}
            for entry in hash_entries:
                filename = entry.get('name')
                fileelem = name2elem.get(filename)
                if filename not in sha256sums:
                    msg = 'There is no sha256 sum for file %s.\n' \
                          'This could be due to an outdated working copy.\n' \
                          'Please update your working copy with osc update and\n' \
                          'commit again afterwards.'
                    print(msg % filename)
                    return 1
                fileelem.set('hash', f'sha256:{sha256sums[filename]}')
            sfilelist = self.__send_commitlog(msg, filelist)
        send = self.commit_get_missing(sfilelist)
        real_send = [i for i in real_send if i not in send]
        # abort after 3 tries
        tries = 3
        tdir = None
        try:
            tdir = os.path.join(self.storedir, '_in_commit')
            if os.path.isdir(tdir):
                shutil.rmtree(tdir)
            os.mkdir(tdir)
            while send and tries:
                for filename in send[:]:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                    self.put_source_file(filename, tdir)
                    send.remove(filename)
                tries -= 1
                sfilelist = self.__send_commitlog(msg, filelist)
                send = self.commit_get_missing(sfilelist)
            if send:
                raise oscerr.PackageInternalError(self.prjname, self.name,
                                                  'server does not accept filelist:\n%s\nmissing:\n%s\n'
                                                  % (ET.tostring(filelist, encoding=ET_ENCODING), ET.tostring(sfilelist, encoding=ET_ENCODING)))
            # these files already exist on the server
            for filename in real_send:
                self.put_source_file(filename, tdir, copy_only=True)
            # update store with the committed files
            self.__commit_update_store(tdir)
        finally:
            if tdir is not None and os.path.isdir(tdir):
                shutil.rmtree(tdir)
        self.rev = sfilelist.get('rev')
        print()
        print(f'Committed revision {self.rev}.')

        if self.ispulled():
            os.unlink(os.path.join(self.storedir, '_pulled'))
        if self.islinkrepair():
            os.unlink(os.path.join(self.storedir, '_linkrepair'))
            self.linkrepair = False
            # XXX: mark package as invalid?
            print('The source link has been repaired. This directory can now be removed.')

        if self.islink() and self.isexpanded():
            li = Linkinfo()
            li.read(sfilelist.find('linkinfo'))
            if li.xsrcmd5 is None:
                raise oscerr.APIError(f'linkinfo has no xsrcmd5 attr:\n{ET.tostring(sfilelist, encoding=ET_ENCODING)}\n')
            sfilelist = xml_fromstring(self.get_files_meta(revision=li.xsrcmd5))
        for i in sfilelist.findall('entry'):
            if i.get('name') in self.skipped:
                i.set('skipped', 'true')
        store_write_string(self.absdir, '_files', ET.tostring(sfilelist, encoding=ET_ENCODING) + '\n')
        for filename in todo_delete:
            self.to_be_deleted.remove(filename)
            self.store.sources_delete_file(filename)
        self.write_deletelist()
        self.write_addlist()
        self.update_datastructs()

        print_request_list(self.apiurl, self.prjname, self.name)

        # FIXME: add testcases for this codepath
        sinfo = sfilelist.find('serviceinfo')
        if sinfo is not None:
            print('Waiting for server side source service run')
            u = makeurl(self.apiurl, ['source', self.prjname, self.name])
            while sinfo is not None and sinfo.get('code') == 'running':
                sys.stdout.write('.')
                sys.stdout.flush()
                # does it make sense to add some delay?
                sfilelist = xml_fromstring(http_GET(u).read())
                # if sinfo is None another commit might have occured in the "meantime"
                sinfo = sfilelist.find('serviceinfo')
            print('')
            rev = self.latest_rev()
            self.update(rev=rev)
        elif self.get_local_meta() is None:
            # if this was a newly added package there is no _meta
            # file
            self.update_local_pacmeta()

    def __write_storelist(self, name, data):
        if len(data) == 0:
            try:
                os.unlink(os.path.join(self.storedir, name))
            except:
                pass
        else:
            store_write_string(self.absdir, name, '%s\n' % '\n'.join(data))

    def write_conflictlist(self):
        self.__write_storelist('_in_conflict', self.in_conflict)

    def updatefile(self, n, revision, mtime=None):
        from ..core import get_source_file
        from ..core import utime

        filename = os.path.join(self.dir, n)
        storefilename = self.store.sources_get_path(n)
        origfile_tmp = os.path.join(self.storedir, '_in_update', f'{n}.copy')
        origfile = os.path.join(self.storedir, '_in_update', n)
        if os.path.isfile(filename):
            shutil.copyfile(filename, origfile_tmp)
            os.rename(origfile_tmp, origfile)
        else:
            origfile = None

        get_source_file(self.apiurl, self.prjname, self.name, n, targetfilename=storefilename,
                        revision=revision, progress_obj=self.progress_obj, mtime=mtime, meta=self.meta)

        shutil.copyfile(storefilename, filename)
        if mtime:
            utime(filename, (-1, mtime))
        if origfile is not None:
            os.unlink(origfile)

    def mergefile(self, n, revision, mtime=None):
        from ..core import binary_file
        from ..core import get_source_file
        from ..core import run_external

        filename = os.path.join(self.dir, n)
        storefilename = self.store.sources_get_path(n)
        myfilename = os.path.join(self.dir, n + '.mine')
        upfilename = os.path.join(self.dir, n + '.new')
        origfile_tmp = os.path.join(self.storedir, '_in_update', f'{n}.copy')
        origfile = os.path.join(self.storedir, '_in_update', n)
        shutil.copyfile(filename, origfile_tmp)
        os.rename(origfile_tmp, origfile)
        os.rename(filename, myfilename)

        get_source_file(self.apiurl, self.prjname, self.name, n,
                        revision=revision, targetfilename=upfilename,
                        progress_obj=self.progress_obj, mtime=mtime, meta=self.meta)

        if binary_file(myfilename) or binary_file(upfilename):
            # don't try merging
            shutil.copyfile(upfilename, filename)
            shutil.copyfile(upfilename, storefilename)
            os.unlink(origfile)
            self.in_conflict.append(n)
            self.write_conflictlist()
            return 'C'
        else:
            # try merging
            # diff3 OPTIONS... MINE OLDER YOURS
            ret = -1
            with open(filename, 'w') as f:
                args = ('-m', '-E', myfilename, storefilename, upfilename)
                ret = run_external('diff3', *args, stdout=f)

            #   "An exit status of 0 means `diff3' was successful, 1 means some
            #   conflicts were found, and 2 means trouble."
            if ret == 0:
                # merge was successful... clean up
                shutil.copyfile(upfilename, storefilename)
                os.unlink(upfilename)
                os.unlink(myfilename)
                os.unlink(origfile)
                return 'G'
            elif ret == 1:
                # unsuccessful merge
                shutil.copyfile(upfilename, storefilename)
                os.unlink(origfile)
                self.in_conflict.append(n)
                self.write_conflictlist()
                return 'C'
            else:
                merge_cmd = 'diff3 ' + ' '.join(args)
                raise oscerr.ExtRuntimeError(f'diff3 failed with exit code: {ret}', merge_cmd)

    def update_local_filesmeta(self, revision=None):
        """
        Update the local _files file in the store.
        It is replaced with the version pulled from upstream.
        """
        meta = self.get_files_meta(revision=revision)
        store_write_string(self.absdir, '_files', meta + '\n')

    def get_files_meta(self, revision='latest', skip_service=True):
        from ..core import ET_ENCODING
        from ..core import show_files_meta

        fm = show_files_meta(self.apiurl, self.prjname, self.name, revision=revision, meta=self.meta)
        # look for "too large" files according to size limit and mark them
        root = xml_fromstring(fm)
        for e in root.findall('entry'):
            size = e.get('size')
            if size and self.size_limit and int(size) > self.size_limit \
                    or skip_service and (e.get('name').startswith('_service:') or e.get('name').startswith('_service_')):
                e.set('skipped', 'true')
                continue

            if conf.config["exclude_files"]:
                exclude = False
                for pattern in conf.config["exclude_files"]:
                    if fnmatch.fnmatch(e.get("name"), pattern):
                        exclude = True
                        break
                if exclude:
                    e.set("skipped", "true")
                    continue

            if conf.config["include_files"]:
                include = False
                for pattern in conf.config["include_files"]:
                    if fnmatch.fnmatch(e.get("name"), pattern):
                        include = True
                        break
                if not include:
                    e.set("skipped", "true")
                    continue

        return ET.tostring(root, encoding=ET_ENCODING)

    def get_local_meta(self):
        """Get the local _meta file for the package."""
        meta = store_read_file(self.absdir, '_meta')
        return meta

    def get_local_origin_project(self):
        """Get the originproject from the _meta file."""
        # if the wc was checked out via some old osc version
        # there might be no meta file: in this case we assume
        # that the origin project is equal to the wc's project
        meta = self.get_local_meta()
        if meta is None:
            return self.prjname
        root = xml_fromstring(meta)
        return root.get('project')

    def is_link_to_different_project(self):
        """Check if the package is a link to a different project."""
        if self.name == "_project":
            return False
        orgprj = self.get_local_origin_project()
        return self.prjname != orgprj

    def update_datastructs(self):
        """
        Update the internal data structures if the local _files
        file has changed (e.g. update_local_filesmeta() has been
        called).
        """
        from ..core import DirectoryServiceinfo

        if self.scm_url:
            self.filenamelist = []
            self.filelist = []
            self.skipped = []
            self.to_be_added = []
            self.to_be_deleted = []
            self.in_conflict = []
            self.linkrepair = None
            self.rev = None
            self.srcmd5 = None
            self.linkinfo = Linkinfo()
            self.serviceinfo = DirectoryServiceinfo()
            self.size_limit = None
            self.meta = None
            self.excluded = []
            self.filenamelist_unvers = []
            return

        files_tree = read_filemeta(self.dir)
        files_tree_root = files_tree.getroot()

        self.rev = files_tree_root.get('rev')
        self.srcmd5 = files_tree_root.get('srcmd5')

        self.linkinfo = Linkinfo()
        self.linkinfo.read(files_tree_root.find('linkinfo'))
        self.serviceinfo = DirectoryServiceinfo()
        self.serviceinfo.read(files_tree_root.find('serviceinfo'))
        self.filenamelist = []
        self.filelist = []
        self.skipped = []

        for node in files_tree_root.findall('entry'):
            try:
                f = File(node.get('name'),
                         node.get('md5'),
                         int(node.get('size')),
                         int(node.get('mtime')))
                if node.get('skipped'):
                    self.skipped.append(f.name)
                    f.skipped = True
            except:
                # okay, a very old version of _files, which didn't contain any metadata yet...
                f = File(node.get('name'), '', 0, 0)
            self.filelist.append(f)
            self.filenamelist.append(f.name)

        self.to_be_added = read_tobeadded(self.absdir)
        self.to_be_deleted = read_tobedeleted(self.absdir)
        self.in_conflict = read_inconflict(self.absdir)
        self.linkrepair = os.path.isfile(os.path.join(self.storedir, '_linkrepair'))
        self.size_limit = read_sizelimit(self.dir)
        self.meta = self.ismetamode()

        # gather unversioned files, but ignore some stuff
        self.excluded = []
        for i in os.listdir(self.dir):
            for j in conf.config['exclude_glob']:
                if fnmatch.fnmatch(i, j):
                    self.excluded.append(i)
                    break
        self.filenamelist_unvers = [i for i in os.listdir(self.dir)
                                    if i not in self.excluded
                                    if i not in self.filenamelist]

    def islink(self):
        """tells us if the package is a link (has 'linkinfo').
        A package with linkinfo is a package which links to another package.
        Returns ``True`` if the package is a link, otherwise ``False``."""
        return self.linkinfo.islink()

    def isexpanded(self):
        """tells us if the package is a link which is expanded.
        Returns ``True`` if the package is expanded, otherwise ``False``."""
        return self.linkinfo.isexpanded()

    def islinkrepair(self):
        """tells us if we are repairing a broken source link."""
        return self.linkrepair

    def ispulled(self):
        """tells us if we have pulled a link."""
        return os.path.isfile(os.path.join(self.storedir, '_pulled'))

    def isfrozen(self):
        """tells us if the link is frozen."""
        return os.path.isfile(os.path.join(self.storedir, '_frozenlink'))

    def ismetamode(self):
        """tells us if the package is in meta mode"""
        return os.path.isfile(os.path.join(self.storedir, '_meta_mode'))

    def get_pulled_srcmd5(self):
        pulledrev = None
        for line in open(os.path.join(self.storedir, '_pulled')):
            pulledrev = line.strip()
        return pulledrev

    def haslinkerror(self):
        """
        Returns ``True`` if the link is broken otherwise ``False``.
        If the package is not a link it returns ``False``.
        """
        return self.linkinfo.haserror()

    def linkerror(self):
        """
        Returns an error message if the link is broken otherwise ``None``.
        If the package is not a link it returns ``None``.
        """
        return self.linkinfo.error

    def hasserviceinfo(self):
        """
        Returns ``True``, if this package contains services.
        """
        return self.serviceinfo.lsrcmd5 is not None or self.serviceinfo.xsrcmd5 is not None

    def update_local_pacmeta(self):
        """
        Update the local _meta file in the store.
        It is replaced with the version pulled from upstream.
        """
        from ..core import show_package_meta

        meta = show_package_meta(self.apiurl, self.prjname, self.name)
        if meta != "":
            # is empty for _project for example
            meta = b''.join(meta)
            store_write_string(self.absdir, '_meta', meta + b'\n')

    def findfilebyname(self, n):
        for i in self.filelist:
            if i.name == n:
                return i

    def get_status(self, excluded=False, *exclude_states):
        global store
        todo = self.todo
        if not todo:
            todo = self.filenamelist + self.to_be_added + \
                [i for i in self.filenamelist_unvers if not os.path.isdir(os.path.join(self.absdir, i))]
            if excluded:
                todo.extend([i for i in self.excluded if i != store])
            todo = set(todo)
        res = []
        for fname in sorted(todo):
            st = self.status(fname)
            if st not in exclude_states:
                res.append((st, fname))
        return res

    def status(self, n):
        """
        status can be::

             file  storefile  file present  STATUS
            exists  exists      in _files
              x       -            -        'A' and listed in _to_be_added
              x       x            -        'R' and listed in _to_be_added
              x       x            x        ' ' if digest differs: 'M'
                                                and if in conflicts file: 'C'
              x       -            -        '?'
              -       x            x        'D' and listed in _to_be_deleted
              x       x            x        'D' and listed in _to_be_deleted (e.g. if deleted file was modified)
              x       x            x        'C' and listed in _in_conflict
              x       -            x        'S' and listed in self.skipped
              -       -            x        'S' and listed in self.skipped
              -       x            x        '!'
              -       -            -        NOT DEFINED
        """
        from ..core import dgst

        known_by_meta = False
        exists = False
        exists_in_store = False
        localfile = os.path.join(self.absdir, n)
        if n in self.filenamelist:
            known_by_meta = True
        if os.path.exists(localfile):
            exists = True
        if self.store.sources_is_file(n):
            exists_in_store = True

        if n in self.to_be_deleted:
            state = 'D'
        elif n in self.in_conflict:
            state = 'C'
        elif n in self.skipped:
            state = 'S'
        elif n in self.to_be_added and exists and exists_in_store:
            state = 'R'
        elif n in self.to_be_added and exists:
            state = 'A'
        elif exists and exists_in_store and known_by_meta:
            filemeta = self.findfilebyname(n)
            state = ' '
            if conf.config['status_mtime_heuristic']:
                if os.path.getmtime(localfile) != filemeta.mtime and dgst(localfile) != filemeta.md5:
                    state = 'M'
            elif dgst(localfile) != filemeta.md5:
                state = 'M'
        elif n in self.to_be_added and not exists:
            state = '!'
        elif not exists and exists_in_store and known_by_meta and n not in self.to_be_deleted:
            state = '!'
        elif exists and not exists_in_store and not known_by_meta:
            state = '?'
        elif not exists_in_store and known_by_meta:
            # XXX: this codepath shouldn't be reached (we restore the storefile
            #      in update_datastructs)
            raise oscerr.PackageInternalError(self.prjname, self.name,
                                              'error: file \'%s\' is known by meta but no storefile exists.\n'
                                              'This might be caused by an old wc format. Please backup your current\n'
                                              'wc and checkout the package again. Afterwards copy all files (except the\n'
                                              '.osc/ dir) into the new package wc.' % n)
        elif os.path.islink(localfile):
            # dangling symlink, whose name is _not_ tracked: treat it
            # as unversioned
            state = '?'
        else:
            # this case shouldn't happen (except there was a typo in the filename etc.)
            raise oscerr.OscIOError(None, f'osc: \'{n}\' is not under version control')

        return state

    def get_diff(self, revision=None, ignoreUnversioned=False):
        from ..core import binary_file
        from ..core import get_source_file
        from ..core import get_source_file_diff
        from ..core import revision_is_empty

        diff_hdr = b'Index: %s\n'
        diff_hdr += b'===================================================================\n'
        kept = []
        added = []
        deleted = []

        def diff_add_delete(fname, add, revision):
            diff = []
            diff.append(diff_hdr % fname.encode())
            origname = fname
            if add:
                diff.append(b'--- %s\t(revision 0)\n' % fname.encode())
                rev = 'revision 0'
                if not revision_is_empty(revision) and fname not in self.to_be_added:
                    rev = 'working copy'
                diff.append(b'+++ %s\t(%s)\n' % (fname.encode(), rev.encode()))
                fname = os.path.join(self.absdir, fname)
                if not os.path.isfile(fname):
                    raise oscerr.OscIOError(None, 'file \'%s\' is marked as \'A\' but does not exist\n'
                                            '(either add the missing file or revert it)' % fname)
            else:
                if not revision_is_empty(revision):
                    b_revision = str(revision).encode()
                else:
                    b_revision = self.rev.encode()
                diff.append(b'--- %s\t(revision %s)\n' % (fname.encode(), b_revision))
                diff.append(b'+++ %s\t(working copy)\n' % fname.encode())
                fname = self.store.sources_get_path(fname)

            fd = None
            tmpfile = None
            try:
                if not revision_is_empty(revision) and not add:
                    (fd, tmpfile) = tempfile.mkstemp(prefix='osc_diff')
                    get_source_file(self.apiurl, self.prjname, self.name, origname, tmpfile, revision)
                    fname = tmpfile
                if binary_file(fname):
                    what = b'added'
                    if not add:
                        what = b'deleted'
                    diff = diff[:1]
                    diff.append(b'Binary file \'%s\' %s.\n' % (origname.encode(), what))
                    return diff
                tmpl = b'+%s'
                ltmpl = b'@@ -0,0 +1,%d @@\n'
                if not add:
                    tmpl = b'-%s'
                    ltmpl = b'@@ -1,%d +0,0 @@\n'
                with open(fname, 'rb') as f:
                    lines = [tmpl % i for i in f.readlines()]
                if len(lines):
                    diff.append(ltmpl % len(lines))
                    if not lines[-1].endswith(b'\n'):
                        lines.append(b'\n\\ No newline at end of file\n')
                diff.extend(lines)
            finally:
                if fd is not None:
                    os.close(fd)
                if tmpfile is not None and os.path.exists(tmpfile):
                    os.unlink(tmpfile)
            return diff

        if revision is None:
            todo = self.todo or [i for i in self.filenamelist if i not in self.to_be_added] + self.to_be_added
            for fname in todo:
                if fname in self.to_be_added and self.status(fname) == 'A':
                    added.append(fname)
                elif fname in self.to_be_deleted:
                    deleted.append(fname)
                elif fname in self.filenamelist:
                    kept.append(self.findfilebyname(fname))
                elif fname in self.to_be_added and self.status(fname) == '!':
                    raise oscerr.OscIOError(None, 'file \'%s\' is marked as \'A\' but does not exist\n'
                                            '(either add the missing file or revert it)' % fname)
                elif not ignoreUnversioned:
                    raise oscerr.OscIOError(None, f'file \'{fname}\' is not under version control')
        else:
            fm = self.get_files_meta(revision=revision)
            root = xml_fromstring(fm)
            rfiles = self.__get_files(root)
            # swap added and deleted
            kept, deleted, added, services = self.__get_rev_changes(rfiles)
            added = [f.name for f in added]
            added.extend([f for f in self.to_be_added if f not in kept])
            deleted = [f.name for f in deleted]
            deleted.extend(self.to_be_deleted)
            for f in added[:]:
                if f in deleted:
                    added.remove(f)
                    deleted.remove(f)
#        print kept, added, deleted
        for f in kept:
            state = self.status(f.name)
            if state in ('S', '?', '!'):
                continue
            elif state == ' ' and revision is None:
                continue
            elif not revision_is_empty(revision) and self.findfilebyname(f.name).md5 == f.md5 and state != 'M':
                continue
            yield [diff_hdr % f.name.encode()]
            if revision is None:
                yield get_source_file_diff(self.absdir, f.name, self.rev)
            else:
                fd = None
                tmpfile = None
                diff = []
                try:
                    (fd, tmpfile) = tempfile.mkstemp(prefix='osc_diff')
                    get_source_file(self.apiurl, self.prjname, self.name, f.name, tmpfile, revision)
                    diff = get_source_file_diff(self.absdir, f.name, revision,
                                                os.path.basename(tmpfile), os.path.dirname(tmpfile), f.name)
                finally:
                    if fd is not None:
                        os.close(fd)
                    if tmpfile is not None and os.path.exists(tmpfile):
                        os.unlink(tmpfile)
                yield diff

        for f in added:
            yield diff_add_delete(f, True, revision)
        for f in deleted:
            yield diff_add_delete(f, False, revision)

    def merge(self, otherpac):
        for todo_entry in otherpac.todo:
            if todo_entry not in self.todo:
                self.todo.append(todo_entry)

    def __str__(self):
        r = """
name: %s
prjname: %s
workingdir: %s
localfilelist: %s
linkinfo: %s
rev: %s
'todo' files: %s
""" % (self.name,
            self.prjname,
            self.dir,
            '\n               '.join(self.filenamelist),
            self.linkinfo,
            self.rev,
            self.todo)

        return r

    def read_meta_from_spec(self, spec=None):
        from  ..core import read_meta_from_spec

        if spec:
            specfile = spec
        else:
            # scan for spec files
            speclist = glob.glob(os.path.join(self.dir, '*.spec'))
            if len(speclist) == 1:
                specfile = speclist[0]
            elif len(speclist) > 1:
                print('the following specfiles were found:')
                for filename in speclist:
                    print(filename)
                print('please specify one with --specfile')
                sys.exit(1)
            else:
                print('no specfile was found - please specify one '
                      'with --specfile')
                sys.exit(1)

        data = read_meta_from_spec(specfile, 'Summary', 'Url', '%description')
        self.summary = data.get('Summary', '')
        self.url = data.get('Url', '')
        self.descr = data.get('%description', '')

    def update_package_meta(self, force=False):
        """
        for the updatepacmetafromspec subcommand
            argument force supress the confirm question
        """
        from .. import obs_api
        from ..output import get_user_input

        package_obj = obs_api.Package.from_api(self.apiurl, self.prjname, self.name)
        old = package_obj.to_string()
        package_obj.title = self.summary.strip()
        package_obj.description = "".join(self.descr).strip()
        package_obj.url = self.url.strip()
        new = package_obj.to_string()

        if not package_obj.has_changed():
            return

        if force:
            reply = "y"
        else:
            while True:
                print("\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile="old", tofile="new")))
                print()

                reply = get_user_input(
                    "Write?",
                    answers={"y": "yes", "n": "no", "e": "edit"},
                )
                if reply == "y":
                    break
                if reply == "n":
                    break
                if reply == "e":
                    _, _, edited_obj = package_obj.do_edit()
                    package_obj.do_update(edited_obj)
                    new = package_obj.to_string()
                    continue

        if reply == "y":
            package_obj.to_api(self.apiurl)

    def mark_frozen(self):
        store_write_string(self.absdir, '_frozenlink', '')
        print()
        print(f"The link in this package (\"{self.name}\") is currently broken. Checking")
        print("out the last working version instead; please use 'osc pull'")
        print("to merge the conflicts.")
        print()

    def unmark_frozen(self):
        if os.path.exists(os.path.join(self.storedir, '_frozenlink')):
            os.unlink(os.path.join(self.storedir, '_frozenlink'))

    def latest_rev(self, include_service_files=False, expand=False):
        from ..core import show_upstream_rev
        from ..core import show_upstream_xsrcmd5

        # if expand is True the xsrcmd5 will be returned (even if the wc is unexpanded)
        if self.islinkrepair():
            upstream_rev = show_upstream_xsrcmd5(self.apiurl, self.prjname, self.name, linkrepair=1, meta=self.meta, include_service_files=include_service_files)
        elif self.islink() and (self.isexpanded() or expand):
            if self.isfrozen() or self.ispulled():
                upstream_rev = show_upstream_xsrcmd5(self.apiurl, self.prjname, self.name, linkrev=self.linkinfo.srcmd5, meta=self.meta, include_service_files=include_service_files)
            else:
                try:
                    upstream_rev = show_upstream_xsrcmd5(self.apiurl, self.prjname, self.name, meta=self.meta, include_service_files=include_service_files)
                except:
                    try:
                        upstream_rev = show_upstream_xsrcmd5(self.apiurl, self.prjname, self.name, linkrev=self.linkinfo.srcmd5, meta=self.meta, include_service_files=include_service_files)
                    except:
                        upstream_rev = show_upstream_xsrcmd5(self.apiurl, self.prjname, self.name, linkrev="base", meta=self.meta, include_service_files=include_service_files)
                    self.mark_frozen()
        elif not self.islink() and expand:
            upstream_rev = show_upstream_xsrcmd5(self.apiurl, self.prjname, self.name, meta=self.meta, include_service_files=include_service_files)
        else:
            upstream_rev = show_upstream_rev(self.apiurl, self.prjname, self.name, meta=self.meta, include_service_files=include_service_files)
        return upstream_rev

    def __get_files(self, fmeta_root):
        from ..core import ET_ENCODING

        f = []
        if fmeta_root.get('rev') is None and len(fmeta_root.findall('entry')) > 0:
            raise oscerr.APIError(f"missing rev attribute in _files:\n{''.join(ET.tostring(fmeta_root, encoding=ET_ENCODING))}")
        for i in fmeta_root.findall('entry'):
            error = i.get('error')
            if error is not None:
                raise oscerr.APIError(f'broken files meta: {error}')
            skipped = i.get('skipped') is not None
            f.append(File(i.get('name'), i.get('md5'),
                     int(i.get('size')), int(i.get('mtime')), skipped))
        return f

    def __get_rev_changes(self, revfiles):
        kept = []
        added = []
        deleted = []
        services = []
        revfilenames = []
        for f in revfiles:
            revfilenames.append(f.name)
            # treat skipped like deleted files
            if f.skipped:
                if f.name.startswith('_service:'):
                    services.append(f)
                else:
                    deleted.append(f)
                continue
            # treat skipped like added files
            # problem: this overwrites existing files during the update
            # (because skipped files aren't in self.filenamelist_unvers)
            if f.name in self.filenamelist and f.name not in self.skipped:
                kept.append(f)
            else:
                added.append(f)
        for f in self.filelist:
            if f.name not in revfilenames:
                deleted.append(f)

        return kept, added, deleted, services

    def update_needed(self, sinfo):
        # this method might return a false-positive (that is a True is returned,
        # even though no update is needed) (for details, see comments below)
        if self.islink():
            if self.isexpanded():
                # check if both revs point to the same expanded sources
                # Note: if the package contains a _service file, sinfo.srcmd5's lsrcmd5
                # points to the "expanded" services (xservicemd5) => chances
                # for a false-positive are high, because osc usually works on the
                # "unexpanded" services.
                # Once the srcserver supports something like noservice=1, we can get rid of
                # this false-positives (patch was already sent to the ml) (but this also
                # requires some slight changes in osc)
                return sinfo.get('srcmd5') != self.srcmd5
            elif self.hasserviceinfo():
                # check if we have expanded or unexpanded services
                if self.serviceinfo.isexpanded():
                    return sinfo.get('lsrcmd5') != self.srcmd5
                else:
                    # again, we might have a false-positive here, because
                    # a mismatch of the "xservicemd5"s does not neccessarily
                    # imply a change in the "unexpanded" services.
                    return sinfo.get('lsrcmd5') != self.serviceinfo.xsrcmd5
            # simple case: unexpanded sources and no services
            # self.srcmd5 should also work
            return sinfo.get('lsrcmd5') != self.linkinfo.lsrcmd5
        elif self.hasserviceinfo():
            if self.serviceinfo.isexpanded():
                return sinfo.get('srcmd5') != self.srcmd5
            else:
                # cannot handle this case, because the sourceinfo does not contain
                # information about the lservicemd5. Once the srcserver supports
                # a noservice=1 query parameter, we can handle this case.
                return True
        return sinfo.get('srcmd5') != self.srcmd5

    def update(self, rev=None, service_files=False, size_limit=None):
        from ..core import ET_ENCODING
        from ..core import dgst

        rfiles = []
        # size_limit is only temporary for this update
        old_size_limit = self.size_limit
        if size_limit is not None:
            self.size_limit = int(size_limit)

        in_update_files_path = os.path.join(self.storedir, "_in_update", "_files")
        if os.path.isfile(in_update_files_path) and os.path.getsize(in_update_files_path) != 0:
            print('resuming broken update...')
            root = xml_parse(os.path.join(self.storedir, '_in_update', '_files')).getroot()
            rfiles = self.__get_files(root)
            kept, added, deleted, services = self.__get_rev_changes(rfiles)
            # check if we aborted in the middle of a file update
            broken_file = os.listdir(os.path.join(self.storedir, '_in_update'))
            broken_file.remove('_files')
            if len(broken_file) == 1:
                origfile = os.path.join(self.storedir, '_in_update', broken_file[0])
                wcfile = os.path.join(self.absdir, broken_file[0])
                origfile_md5 = dgst(origfile)
                origfile_meta = self.findfilebyname(broken_file[0])
                if origfile.endswith('.copy'):
                    # ok it seems we aborted at some point during the copy process
                    # (copy process == copy wcfile to the _in_update dir). remove file+continue
                    os.unlink(origfile)
                elif self.findfilebyname(broken_file[0]) is None:
                    # should we remove this file from _in_update? if we don't
                    # the user has no chance to continue without removing the file manually
                    raise oscerr.PackageInternalError(self.prjname, self.name,
                                                      '\'%s\' is not known by meta but exists in \'_in_update\' dir')
                elif os.path.isfile(wcfile) and dgst(wcfile) != origfile_md5:
                    (fd, tmpfile) = tempfile.mkstemp(dir=self.absdir, prefix=broken_file[0] + '.')
                    os.close(fd)
                    os.rename(wcfile, tmpfile)
                    os.rename(origfile, wcfile)
                    print('warning: it seems you modified \'%s\' after the broken '
                          'update. Restored original file and saved modified version '
                          'to \'%s\'.' % (wcfile, tmpfile))
                elif not os.path.isfile(wcfile):
                    # this is strange... because it existed before the update. restore it
                    os.rename(origfile, wcfile)
                else:
                    # everything seems to be ok
                    os.unlink(origfile)
            elif len(broken_file) > 1:
                raise oscerr.PackageInternalError(self.prjname, self.name, 'too many files in \'_in_update\' dir')
            tmp = rfiles[:]
            for f in tmp:
                if self.store.sources_is_file(f.name):
                    if dgst(self.store.sources_get_path(f.name)) == f.md5:
                        if f in kept:
                            kept.remove(f)
                        elif f in added:
                            added.remove(f)
                        # this can't happen
                        elif f in deleted:
                            deleted.remove(f)
            if not service_files:
                services = []
            self.__update(kept, added, deleted, services, ET.tostring(root, encoding=ET_ENCODING), root.get('rev'))
            os.unlink(os.path.join(self.storedir, '_in_update', '_files'))
            os.rmdir(os.path.join(self.storedir, '_in_update'))
        # ok everything is ok (hopefully)...
        fm = self.get_files_meta(revision=rev)
        root = xml_fromstring(fm)
        rfiles = self.__get_files(root)
        store_write_string(self.absdir, '_files', fm + '\n', subdir='_in_update')
        kept, added, deleted, services = self.__get_rev_changes(rfiles)
        if not service_files:
            services = []
        self.__update(kept, added, deleted, services, fm, root.get('rev'))
        os.unlink(os.path.join(self.storedir, '_in_update', '_files'))
        if os.path.isdir(os.path.join(self.storedir, '_in_update')):
            os.rmdir(os.path.join(self.storedir, '_in_update'))
        self.size_limit = old_size_limit

    def __update(self, kept, added, deleted, services, fm, rev):
        from ..core import get_source_file
        from ..core import getTransActPath
        from ..core import statfrmt

        pathn = getTransActPath(self.dir)
        # check for conflicts with existing files
        for f in added:
            if f.name in self.filenamelist_unvers:
                raise oscerr.PackageFileConflict(self.prjname, self.name, f.name,
                                                 f'failed to add file \'{f.name}\' file/dir with the same name already exists')
        # ok, the update can't fail due to existing files
        for f in added:
            self.updatefile(f.name, rev, f.mtime)
            print(statfrmt('A', os.path.join(pathn, f.name)))
        for f in deleted:
            # if the storefile doesn't exist we're resuming an aborted update:
            # the file was already deleted but we cannot know this
            # OR we're processing a _service: file (simply keep the file)
            if self.store.sources_is_file(f.name) and self.status(f.name) not in ('M', 'C'):
                # if self.status(f.name) != 'M':
                self.delete_localfile(f.name)
            self.store.sources_delete_file(f.name)
            print(statfrmt('D', os.path.join(pathn, f.name)))
            if f.name in self.to_be_deleted:
                self.to_be_deleted.remove(f.name)
                self.write_deletelist()
            elif f.name in self.in_conflict:
                self.in_conflict.remove(f.name)
                self.write_conflictlist()

        for f in kept:
            state = self.status(f.name)
#            print f.name, state
            if state == 'M' and self.findfilebyname(f.name).md5 == f.md5:
                # remote file didn't change
                pass
            elif state == 'M':
                # try to merge changes
                merge_status = self.mergefile(f.name, rev, f.mtime)
                print(statfrmt(merge_status, os.path.join(pathn, f.name)))
            elif state == '!':
                self.updatefile(f.name, rev, f.mtime)
                print(f'Restored \'{os.path.join(pathn, f.name)}\'')
            elif state == 'C':
                get_source_file(self.apiurl, self.prjname, self.name, f.name,
                                targetfilename=self.store.sources_get_path(f.name), revision=rev,
                                progress_obj=self.progress_obj, mtime=f.mtime, meta=self.meta)
                print(f'skipping \'{f.name}\' (this is due to conflicts)')
            elif state == 'D' and self.findfilebyname(f.name).md5 != f.md5:
                # XXX: in the worst case we might end up with f.name being
                # in _to_be_deleted and in _in_conflict... this needs to be checked
                if os.path.exists(os.path.join(self.absdir, f.name)):
                    merge_status = self.mergefile(f.name, rev, f.mtime)
                    print(statfrmt(merge_status, os.path.join(pathn, f.name)))
                    if merge_status == 'C':
                        # state changes from delete to conflict
                        self.to_be_deleted.remove(f.name)
                        self.write_deletelist()
                else:
                    # XXX: we cannot recover this case because we've no file
                    # to backup
                    self.updatefile(f.name, rev, f.mtime)
                    print(statfrmt('U', os.path.join(pathn, f.name)))
            elif state == ' ' and self.findfilebyname(f.name).md5 != f.md5:
                self.updatefile(f.name, rev, f.mtime)
                print(statfrmt('U', os.path.join(pathn, f.name)))

        # checkout service files
        for f in services:
            get_source_file(self.apiurl, self.prjname, self.name, f.name,
                            targetfilename=os.path.join(self.absdir, f.name), revision=rev,
                            progress_obj=self.progress_obj, mtime=f.mtime, meta=self.meta)
            print(statfrmt('A', os.path.join(pathn, f.name)))
        store_write_string(self.absdir, '_files', fm + '\n')
        if not self.meta:
            self.update_local_pacmeta()
        self.update_datastructs()

        print(f'At revision {self.rev}.')

    def run_source_services(self, mode=None, singleservice=None, verbose=None):
        if self.name.startswith("_"):
            return 0
        curdir = os.getcwd()
        os.chdir(self.absdir)  # e.g. /usr/lib/obs/service/verify_file fails if not inside the project dir.
        si = Serviceinfo()
        if os.path.exists('_service'):
            try:
                service = xml_parse(os.path.join(self.absdir, '_service')).getroot()
            except ET.ParseError as v:
                line, column = v.position
                print(f'XML error in _service file on line {line}, column {column}')
                sys.exit(1)
            si.read(service)
        si.getProjectGlobalServices(self.apiurl, self.prjname, self.name)
        r = si.execute(self.absdir, mode, singleservice, verbose)
        os.chdir(curdir)
        return r

    def revert(self, filename):
        if filename not in self.filenamelist and filename not in self.to_be_added:
            raise oscerr.OscIOError(None, f'file \'{filename}\' is not under version control')
        elif filename in self.skipped:
            raise oscerr.OscIOError(None, f'file \'{filename}\' is marked as skipped and cannot be reverted')
        if filename in self.filenamelist and not self.store.sources_is_file(filename):
            msg = f"file '{filename}' is listed in filenamelist but no storefile exists"
            raise oscerr.PackageInternalError(self.prjname, self.name, msg)
        state = self.status(filename)
        if not (state == 'A' or state == '!' and filename in self.to_be_added):
            shutil.copyfile(self.store.sources_get_path(filename), os.path.join(self.absdir, filename))
        if state == 'D':
            self.to_be_deleted.remove(filename)
            self.write_deletelist()
        elif state == 'C':
            self.clear_from_conflictlist(filename)
        elif state in ('A', 'R') or state == '!' and filename in self.to_be_added:
            self.to_be_added.remove(filename)
            self.write_addlist()

    @staticmethod
    def init_package(apiurl: str, project, package, dir, size_limit=None, meta=False, progress_obj=None, scm_url=None):
        global store

        if not os.path.exists(dir):
            os.mkdir(dir)
        elif not os.path.isdir(dir):
            raise oscerr.OscIOError(None, f'error: \'{dir}\' is no directory')
        if os.path.exists(os.path.join(dir, store)):
            raise oscerr.OscIOError(None, f'error: \'{dir}\' is already an initialized osc working copy')
        else:
            os.mkdir(os.path.join(dir, store))

        s = Store(dir, check=False)
        s.write_string("_osclib_version", Store.STORE_VERSION)
        s.apiurl = apiurl
        s.project = project
        s.package = package
        if meta:
            s.write_string("_meta_mode", "")
        if size_limit:
            s.size_limit = int(size_limit)
        if scm_url:
            s.scmurl = scm_url
        else:
            s.write_string("_files", "<directory />")
        return Package(dir, progress_obj=progress_obj, size_limit=size_limit)
