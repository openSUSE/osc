Tutorial
========

This is a tutorial on how to use the osc python api.

Key to the |obs| are (remote):
    
    #. A **project**
    #. A project has associated multiple **repositories** (linux distributions)
    #. Multiple **packages** in a project will hold the builds against the difefrent **repositories**


A user will deal with local checkout of a project in a **working copy**: this is similar to the 
subversion checkout model.


Initial config setup
--------------------

Osc the library requires an initial setup:

    >>> import osc.conf
    >>> osc.conf.get_config()

This will read all the external config files (eg. ~/.oscrc) and the internal configuration 
values.


Acquiring the apiurl 
--------------------

All the osc operation will use a **apiurl** to lookup for things like passwords, username and other parameters
while performing operations:

    >>> apiurl = osc.conf.config['apiurl']


Operations on a remote build server
-----------------------------------

osc is similar to subversion, it has a remote server and a local (checkout) **working** directory.
First we'll go through the remote operation on a server **NOT** requiring a checkout.
Operations are contained in the osc.core module:

    >>> import osc.core


List all the projects and packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This will show all the projects on the remote |obs|:

    >>> for prj in osc.core.meta_get_project_list(apiurl, deleted=False):
            print(prj)


A project has **repositories** associated with it (eg. linux distributions):

    >>> prj = 'home:cavallo71:opt-python-interpreters'
    >>> for repo in osc.core.get_repos_of_project(apiurl, prj):
            print(repo)


A project contains packages and to list them all:
    
    >>> prj = 'home:cavallo71:opt-python-interpreters'
    >>> for pkg in osc.core.meta_get_packagelist(apiurl, prj):
            print(pkg)


Add a package to an existing project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Operations in a checked out **working copy**
--------------------------------------------



Create your first project: the hello project
--------------------------------------------

.. todo:: add he description on how to init a project


Adding your firs package to the project hello: the world package
----------------------------------------------------------------

.. todo:: add he description on how to add a package



Setting the build architectures
-------------------------------


