import fnmatch
import os
from pathlib import Path
from typing import Optional

from .. import conf
from .. import oscerr
from ..util.xml import ET
from ..util.xml import xml_parse
from .store import Store
from .store import delete_storedir
from .store import store
from .store import store_read_package
from .store import store_read_project
from .store import store_write_initial_packages
from .store import store_write_project
from .store import store_write_string
from .store import is_package_dir


class Project:
    """
    Represent a checked out project directory, holding packages.

    :Attributes:
        ``dir``
            The directory path containing the project.

        ``name``
            The name of the project.

        ``apiurl``
            The endpoint URL of the API server.

        ``pacs_available``
            List of names of packages available server-side.
            This is only populated if ``getPackageList`` is set
            to ``True`` in the constructor.

        ``pacs_have``
            List of names of packages which exist server-side
            and exist in the local project working copy (if
            'do_package_tracking' is disabled).
            If 'do_package_tracking' is enabled it represents the
            list names of packages which are tracked in the project
            working copy (that is it might contain packages which
            exist on the server as well as packages which do not
            exist on the server (for instance if the local package
            was added or if the package was removed on the server-side)).

        ``pacs_excluded``
            List of names of packages in the local project directory
            which are excluded by the `exclude_glob` configuration
            variable.  Only set if `do_package_tracking` is enabled.

        ``pacs_unvers``
            List of names of packages in the local project directory
            which are not tracked. Only set if `do_package_tracking`
            is enabled.

        ``pacs_broken``
            List of names of packages which are tracked but do not
            exist in the local project working copy. Only set if
            `do_package_tracking` is enabled.

        ``pacs_missing``
            List of names of packages which exist server-side but
            are not expected to exist in the local project directory.
    """

    REQ_STOREFILES = ('_project', '_apiurl')

    def __init__(self, dir, getPackageList=True, progress_obj=None, wc_check=True):
        """
        Constructor.

        :Parameters:
            `dir` : str
                The directory path containing the checked out project.

            `getPackageList` : bool
                Set to `False` if you want to skip retrieval from the
                server of the list of packages in the project .

            `wc_check` : bool
        """
        from ..core import meta_get_packagelist

        self.dir = Path(dir)
        self.absdir = os.path.abspath(dir)
        self.store = Store(dir, check=wc_check)
        self.progress_obj = progress_obj

        self.name = store_read_project(self.dir)
        self.scm_url = self.store.scmurl
        self.apiurl = self.store.apiurl

        dirty_files = []
        if wc_check:
            dirty_files = self.wc_check()
        if dirty_files:
            msg = 'Your working copy \'%s\' is in an inconsistent state.\n' \
                'Please run \'osc repairwc %s\' and check the state\n' \
                'of the working copy afterwards (via \'osc status %s\')' % (self.dir, self.dir, self.dir)
            raise oscerr.WorkingCopyInconsistent(self.name, None, dirty_files, msg)

        if getPackageList:
            self.pacs_available = meta_get_packagelist(self.apiurl, self.name)
        else:
            self.pacs_available = []

        if conf.config['do_package_tracking']:
            self.pac_root = self.read_packages().getroot()
            self.pacs_have = [pac.get('name') for pac in self.pac_root.findall('package')]
            self.pacs_excluded = [i for i in os.listdir(self.dir)
                                  for j in conf.config['exclude_glob']
                                  if fnmatch.fnmatch(i, j)]
            self.pacs_unvers = [i for i in os.listdir(self.dir) if i not in self.pacs_have and i not in self.pacs_excluded]
            # store all broken packages (e.g. packages which where removed by a non-osc cmd)
            # in the self.pacs_broken list
            self.pacs_broken = []
            for p in self.pacs_have:
                if not os.path.isdir(os.path.join(self.absdir, p)):
                    # all states will be replaced with the '!'-state
                    # (except it is already marked as deleted ('D'-state))
                    self.pacs_broken.append(p)
        else:
            self.pacs_have = [i for i in os.listdir(self.dir) if i in self.pacs_available]

        self.pacs_missing = [i for i in self.pacs_available if i not in self.pacs_have]

    def wc_check(self):
        global store
        dirty_files = []
        req_storefiles = Project.REQ_STOREFILES
        if conf.config['do_package_tracking'] and self.scm_url is None:
            req_storefiles += ('_packages',)
        for fname in req_storefiles:
            if not os.path.exists(os.path.join(self.absdir, store, fname)):
                dirty_files.append(fname)
        return dirty_files

    def wc_repair(self, apiurl: Optional[str] = None) -> bool:
        repaired: bool = False

        store = Store(self.dir, check=False)
        store.assert_is_project()

        # there was a time when osc did not write _osclib_version file; let's assume these checkouts have version 1.0
        if not store.exists("_osclib_version"):
            store.write_string("_osclib_version", "1.0")
            repaired = True

        if not store.exists("_apiurl") or apiurl:
            if apiurl is None:
                msg = 'cannot repair wc: the \'_apiurl\' file is missing but ' \
                    'no \'apiurl\' was passed to wc_repair'
                # hmm should we raise oscerr.WrongArgs?
                raise oscerr.WorkingCopyInconsistent(self.name, None, [], msg)
            # sanity check
            conf.parse_apisrv_url(None, apiurl)
            store.apiurl = apiurl
            self.apiurl = apiurl
            repaired = True

        return repaired

    def checkout_missing_pacs(self, sinfos, expand_link=False, unexpand_link=False):
        from ..core import checkout_package
        from ..core import getTransActPath

        for pac in self.pacs_missing:
            if conf.config['do_package_tracking'] and pac in self.pacs_unvers:
                # pac is not under version control but a local file/dir exists
                msg = f'can\'t add package \'{pac}\': Object already exists'
                raise oscerr.PackageExists(self.name, pac, msg)

            if not (expand_link or unexpand_link):
                sinfo = sinfos.get(pac)
                if sinfo is None:
                    # should never happen...
                    continue
                linked = sinfo.find('linked')
                if linked is not None and linked.get('project') == self.name:
                    # hmm what about a linkerror (sinfo.get('lsrcmd5') is None)?
                    # Should we skip the package as well or should we it out?
                    # let's skip it for now
                    print(f"Skipping {pac} (link to package {linked.get('package')})")
                    continue

            print(f'checking out new package {pac}')
            checkout_package(self.apiurl, self.name, pac,
                             pathname=getTransActPath(os.path.join(self.dir, pac)),
                             prj_obj=self, prj_dir=self.dir,
                             expand_link=expand_link or not unexpand_link, progress_obj=self.progress_obj)

    def status(self, pac: str):
        exists = os.path.exists(os.path.join(self.absdir, pac))
        st = self.get_state(pac)
        if st is None and exists:
            return '?'
        elif st is None:
            raise oscerr.OscIOError(None, f'osc: \'{pac}\' is not under version control')
        elif st in ('A', ' ') and not exists:
            return '!'
        elif st == 'D' and not exists:
            return 'D'
        else:
            return st

    def get_status(self, *exclude_states):
        res = []
        for pac in self.pacs_have:
            st = self.status(pac)
            if st not in exclude_states:
                res.append((st, pac))
        if '?' not in exclude_states:
            res.extend([('?', pac) for pac in self.pacs_unvers])
        return res

    def get_pacobj(self, pac, *pac_args, **pac_kwargs):
        from ..core import Package

        try:
            st = self.status(pac)
            if st in ('?', '!') or st == 'D' and not os.path.exists(os.path.join(self.dir, pac)):
                return None
            return Package(os.path.join(self.dir, pac), *pac_args, **pac_kwargs)
        except oscerr.OscIOError:
            return None

    def set_state(self, pac, state):
        node = self.get_package_node(pac)
        if node is None:
            self.new_package_entry(pac, state)
        else:
            node.set('state', state)

    def get_package_node(self, pac: str):
        for node in self.pac_root.findall('package'):
            if pac == node.get('name'):
                return node
        return None

    def del_package_node(self, pac):
        for node in self.pac_root.findall('package'):
            if pac == node.get('name'):
                self.pac_root.remove(node)

    def get_state(self, pac: str):
        node = self.get_package_node(pac)
        if node is not None:
            return node.get('state')
        else:
            return None

    def info(self):
        from ..core import project_info_templ
        from ..core import makeurl

        source_url = makeurl(self.apiurl, ['source', self.name])
        r = project_info_templ % (self.name, self.absdir, self.apiurl, source_url)
        return r

    def new_package_entry(self, name, state):
        ET.SubElement(self.pac_root, 'package', name=name, state=state)

    def read_packages(self):
        """
        Returns an ``xml.etree.ElementTree`` object representing the
        parsed contents of the project's ``.osc/_packages`` XML file.
        """
        from ..core import Package
        from ..core import meta_get_packagelist

        global store

        packages_file = os.path.join(self.absdir, store, '_packages')
        if os.path.isfile(packages_file) and os.path.getsize(packages_file):
            try:
                result = xml_parse(packages_file)
            except:
                msg = f'Cannot read package file \'{packages_file}\'. '
                msg += 'You can try to remove it and then run osc repairwc.'
                raise oscerr.OscIOError(None, msg)
            return result
        else:
            # scan project for existing packages and migrate them
            cur_pacs = []
            for data in os.listdir(self.dir):
                pac_dir = os.path.join(self.absdir, data)
                # we cannot use self.pacs_available because we cannot guarantee that the package list
                # was fetched from the server
                if data in meta_get_packagelist(self.apiurl, self.name) and is_package_dir(pac_dir) \
                   and Package(pac_dir).name == data:
                    cur_pacs.append(ET.Element('package', name=data, state=' '))
            store_write_initial_packages(self.absdir, self.name, cur_pacs)
            return xml_parse(os.path.join(self.absdir, store, '_packages'))

    def write_packages(self):
        from ..core import ET_ENCODING
        from ..core import xmlindent

        xmlindent(self.pac_root)
        store_write_string(self.absdir, '_packages', ET.tostring(self.pac_root, encoding=ET_ENCODING))

    def addPackage(self, pac):
        for i in conf.config['exclude_glob']:
            if fnmatch.fnmatch(pac, i):
                msg = f'invalid package name: \'{pac}\' (see \'exclude_glob\' config option)'
                raise oscerr.OscIOError(None, msg)
        state = self.get_state(pac)
        if state is None or state == 'D':
            self.new_package_entry(pac, 'A')
            self.write_packages()
            # sometimes the new pac doesn't exist in the list because
            # it would take too much time to update all data structs regularly
            if pac in self.pacs_unvers:
                self.pacs_unvers.remove(pac)
        else:
            raise oscerr.PackageExists(self.name, pac, f'package \'{pac}\' is already under version control')

    def delPackage(self, pac, force=False):
        from ..core import delete_dir
        from ..core import getTransActPath
        from ..core import statfrmt

        state = self.get_state(pac.name)
        can_delete = True
        if state == ' ' or state == 'D':
            del_files = []
            for filename in pac.filenamelist + pac.filenamelist_unvers:
                filestate = pac.status(filename)
                if filestate == 'M' or filestate == 'C' or \
                   filestate == 'A' or filestate == '?':
                    can_delete = False
                else:
                    del_files.append(filename)
            if can_delete or force:
                for filename in del_files:
                    pac.delete_localfile(filename)
                    if pac.status(filename) != '?':
                        # this is not really necessary
                        pac.put_on_deletelist(filename)
                        print(statfrmt('D', getTransActPath(os.path.join(pac.dir, filename))))
                print(statfrmt('D', getTransActPath(os.path.join(pac.dir, os.pardir, pac.name))))
                pac.write_deletelist()
                self.set_state(pac.name, 'D')
                self.write_packages()
            else:
                print(f'package \'{pac.name}\' has local modifications (see osc st for details)')
        elif state == 'A':
            if force:
                delete_dir(pac.absdir)
                self.del_package_node(pac.name)
                self.write_packages()
                print(statfrmt('D', pac.name))
            else:
                print(f'package \'{pac.name}\' has local modifications (see osc st for details)')
        elif state is None:
            print('package is not under version control')
        else:
            print('unsupported state')

    def update(self, pacs=(), expand_link=False, unexpand_link=False, service_files=False):
        from ..core import Package
        from ..core import checkout_package
        from ..core import get_project_sourceinfo
        from ..core import getTransActPath
        from ..core import show_upstream_xsrcmd5

        if pacs:
            for pac in pacs:
                Package(os.path.join(self.dir, pac), progress_obj=self.progress_obj).update()
        else:
            # we need to make sure that the _packages file will be written (even if an exception
            # occurs)
            try:
                # update complete project
                # packages which no longer exists upstream
                upstream_del = [pac for pac in self.pacs_have if pac not in self.pacs_available and self.get_state(pac) != 'A']
                sinfo_pacs = [pac for pac in self.pacs_have if self.get_state(pac) in (' ', 'D') and pac not in self.pacs_broken]
                sinfo_pacs.extend(self.pacs_missing)
                sinfos = get_project_sourceinfo(self.apiurl, self.name, True, *sinfo_pacs)

                for pac in upstream_del:
                    if self.status(pac) != '!':
                        p = Package(os.path.join(self.dir, pac))
                        self.delPackage(p, force=True)
                        delete_storedir(p.storedir)
                        try:
                            os.rmdir(pac)
                        except:
                            pass
                    self.pac_root.remove(self.get_package_node(pac))
                    self.pacs_have.remove(pac)

                for pac in self.pacs_have:
                    state = self.get_state(pac)
                    if pac in self.pacs_broken:
                        if self.get_state(pac) != 'A':
                            checkout_package(self.apiurl, self.name, pac,
                                             pathname=getTransActPath(os.path.join(self.dir, pac)), prj_obj=self,
                                             prj_dir=self.dir, expand_link=not unexpand_link, progress_obj=self.progress_obj)
                    elif state == ' ':
                        # do a simple update
                        p = Package(os.path.join(self.dir, pac), progress_obj=self.progress_obj)
                        rev = None
                        needs_update = True
                        if p.scm_url is not None:
                            # git managed.
                            print("Skipping git managed package ", pac)
                            continue
                        elif expand_link and p.islink() and not p.isexpanded():
                            if p.haslinkerror():
                                try:
                                    rev = show_upstream_xsrcmd5(p.apiurl, p.prjname, p.name, revision=p.rev)
                                except:
                                    rev = show_upstream_xsrcmd5(p.apiurl, p.prjname, p.name, revision=p.rev, linkrev="base")
                                    p.mark_frozen()
                            else:
                                rev = p.linkinfo.xsrcmd5
                            print('Expanding to rev', rev)
                        elif unexpand_link and p.islink() and p.isexpanded():
                            rev = p.linkinfo.lsrcmd5
                            print('Unexpanding to rev', rev)
                        elif p.islink() and p.isexpanded():
                            needs_update = p.update_needed(sinfos[p.name])
                            if needs_update:
                                rev = p.latest_rev()
                        elif p.hasserviceinfo() and p.serviceinfo.isexpanded() and not service_files:
                            # FIXME: currently, do_update does not propagate the --server-side-source-service-files
                            # option to this method. Consequence: an expanded service is always unexpanded during
                            # an update (TODO: discuss if this is a reasonable behavior (at least this the default
                            # behavior for a while))
                            needs_update = True
                        else:
                            needs_update = p.update_needed(sinfos[p.name])
                        print(f'Updating {p.name}')
                        if needs_update:
                            p.update(rev, service_files)
                        else:
                            print(f'At revision {p.rev}.')
                        if unexpand_link:
                            p.unmark_frozen()
                    elif state == 'D':
                        # pac exists (the non-existent pac case was handled in the first if block)
                        p = Package(os.path.join(self.dir, pac), progress_obj=self.progress_obj)
                        if p.update_needed(sinfos[p.name]):
                            p.update()
                    elif state == 'A' and pac in self.pacs_available:
                        # file/dir called pac already exists and is under version control
                        msg = f'can\'t add package \'{pac}\': Object already exists'
                        raise oscerr.PackageExists(self.name, pac, msg)
                    elif state == 'A':
                        # do nothing
                        pass
                    else:
                        print(f'unexpected state.. package \'{pac}\'')

                self.checkout_missing_pacs(sinfos, expand_link, unexpand_link)
            finally:
                self.write_packages()

    def commit(self, pacs=(), msg='', files=None, verbose=False, skip_local_service_run=False, can_branch=False, force=False):
        from ..core import Package
        from ..core import os_path_samefile

        files = files or {}
        if pacs:
            try:
                for pac in pacs:
                    todo = []
                    if pac in files:
                        todo = files[pac]
                    state = self.get_state(pac)
                    if state == 'A':
                        self.commitNewPackage(pac, msg, todo, verbose=verbose, skip_local_service_run=skip_local_service_run)
                    elif state == 'D':
                        self.commitDelPackage(pac, force=force)
                    elif state == ' ':
                        # display the correct dir when sending the changes
                        if os_path_samefile(os.path.join(self.dir, pac), os.getcwd()):
                            p = Package('.')
                        else:
                            p = Package(os.path.join(self.dir, pac))
                        p.todo = todo
                        p.commit(msg, verbose=verbose, skip_local_service_run=skip_local_service_run, can_branch=can_branch, force=force)
                    elif pac in self.pacs_unvers and not is_package_dir(os.path.join(self.dir, pac)):
                        print(f'osc: \'{pac}\' is not under version control')
                    elif pac in self.pacs_broken or not os.path.exists(os.path.join(self.dir, pac)):
                        print(f'osc: \'{pac}\' package not found')
                    elif state is None:
                        self.commitExtPackage(pac, msg, todo, verbose=verbose, skip_local_service_run=skip_local_service_run)
            finally:
                self.write_packages()
        else:
            # if we have packages marked as '!' we cannot commit
            for pac in self.pacs_broken:
                if self.get_state(pac) != 'D':
                    msg = f'commit failed: package \'{pac}\' is missing'
                    raise oscerr.PackageMissing(self.name, pac, msg)
            try:
                for pac in self.pacs_have:
                    state = self.get_state(pac)
                    if state == ' ':
                        # do a simple commit
                        Package(os.path.join(self.dir, pac)).commit(msg, verbose=verbose, skip_local_service_run=skip_local_service_run)
                    elif state == 'D':
                        self.commitDelPackage(pac, force=force)
                    elif state == 'A':
                        self.commitNewPackage(pac, msg, verbose=verbose, skip_local_service_run=skip_local_service_run)
            finally:
                self.write_packages()

    def commitNewPackage(self, pac, msg='', files=None, verbose=False, skip_local_service_run=False):
        """creates and commits a new package if it does not exist on the server"""
        from ..core import Package
        from ..core import edit_meta
        from ..core import os_path_samefile
        from ..core import statfrmt

        files = files or []
        if pac in self.pacs_available:
            print(f'package \'{pac}\' already exists')
        else:
            user = conf.get_apiurl_usr(self.apiurl)
            edit_meta(metatype='pkg',
                      path_args=(self.name, pac),
                      template_args=({
                          'name': pac,
                          'user': user}),
                      apiurl=self.apiurl)
            # display the correct dir when sending the changes
            olddir = os.getcwd()
            if os_path_samefile(os.path.join(self.dir, pac), os.curdir):
                os.chdir(os.pardir)
                p = Package(pac)
            else:
                p = Package(os.path.join(self.dir, pac))
            p.todo = files
            print(statfrmt('Sending', os.path.normpath(p.dir)))
            p.commit(msg=msg, verbose=verbose, skip_local_service_run=skip_local_service_run)
            self.set_state(pac, ' ')
            os.chdir(olddir)

    def commitDelPackage(self, pac, force=False):
        """deletes a package on the server and in the working copy"""

        from ..core import Package
        from ..core import delete_package
        from ..core import getTransActPath
        from ..core import os_path_samefile
        from ..core import statfrmt

        try:
            # display the correct dir when sending the changes
            if os_path_samefile(os.path.join(self.dir, pac), os.curdir):
                pac_dir = pac
            else:
                pac_dir = os.path.join(self.dir, pac)
            p = Package(os.path.join(self.dir, pac))
            # print statfrmt('Deleting', os.path.normpath(os.path.join(p.dir, os.pardir, pac)))
            delete_storedir(p.storedir)
            try:
                os.rmdir(p.dir)
            except:
                pass
        except OSError:
            pac_dir = os.path.join(self.dir, pac)
        except (oscerr.NoWorkingCopy, oscerr.WorkingCopyOutdated, oscerr.PackageError):
            pass
        # print statfrmt('Deleting', getTransActPath(os.path.join(self.dir, pac)))
        print(statfrmt('Deleting', getTransActPath(pac_dir)))
        delete_package(self.apiurl, self.name, pac, force=force)
        self.del_package_node(pac)

    def commitExtPackage(self, pac, msg, files=None, verbose=False, skip_local_service_run=False):
        """commits a package from an external project"""

        from ..core import Package
        from ..core import edit_meta
        from ..core import meta_exists
        from ..core import os_path_samefile

        files = files or []
        if os_path_samefile(os.path.join(self.dir, pac), os.getcwd()):
            pac_path = '.'
        else:
            pac_path = os.path.join(self.dir, pac)

        store = Store(pac_path)
        project = store_read_project(pac_path)
        package = store_read_package(pac_path)
        apiurl = store.apiurl
        if not meta_exists(metatype='pkg',
                           path_args=(project, package),
                           template_args=None, create_new=False, apiurl=apiurl):
            user = conf.get_apiurl_usr(self.apiurl)
            edit_meta(metatype='pkg',
                      path_args=(project, package),
                      template_args=({'name': pac, 'user': user}), apiurl=apiurl)
        p = Package(pac_path)
        p.todo = files
        p.commit(msg=msg, verbose=verbose, skip_local_service_run=skip_local_service_run)

    def __str__(self):
        r = []
        r.append('*****************************************************')
        r.append(f'Project {self.name} (dir={self.dir}, absdir={self.absdir})')
        r.append(f"have pacs:\n{', '.join(self.pacs_have)}")
        r.append(f"missing pacs:\n{', '.join(self.pacs_missing)}")
        r.append('*****************************************************')
        return '\n'.join(r)

    @staticmethod
    def init_project(
        apiurl: str,
        dir: Path,
        project,
        package_tracking=True,
        getPackageList=True,
        progress_obj=None,
        wc_check=True,
        scm_url=None,
    ):
        global store

        if not os.path.exists(dir):
            # use makedirs (checkout_no_colon config option might be enabled)
            os.makedirs(dir)
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
        if scm_url:
            s.scmurl = scm_url
            package_tracking = None
        if package_tracking:
            store_write_initial_packages(dir, project, [])
        return Project(dir, getPackageList, progress_obj, wc_check)
