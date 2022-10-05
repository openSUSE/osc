Prerequisities
--------------
First of all, we need to install requirements:
```
# optional step in case we want to use the latest kanku packages
$ zypper ar obs://devel:kanku:staging devel:kanku:staging

$ cd behave
$ rpmbuild -bs --define='_srcrpmdir .' requirements.spec
$ sudo zypper source-install --build-deps-only ./osc-behave-requirements-1-0.src.rpm
```

Then we need to build 'obs-server' VM using kanku:
```
# necessary if the 'obs-server' domain exists already
$ kanku destroy

$ kanku up [--skip_all_checks]
```


Running tests
-------------

Run all tests
```
$ cd behave
$ behave
```

Run selected tests
```
$ cd behave
$ behave features/<file>.feature
```

Run tests being worked on (decorated with `@wip`)
```
$ cd behave
behave --wip -k
```

Run tests with the selected `osc` executable
```
$ cd behave
behave -Dosc=../osc-wrapper.py
```


Filesystem layout
-----------------

```
<project topdir>
+- behave
     +- features
        +- *.feature       # tests (that use steps defined in the `steps` directory)
                           #   * https://behave.readthedocs.io/en/stable/tutorial.html#feature-files
        +- environment.py  # code that runs before/after certain events (steps, features, etc.)
                           #   * https://behave.readthedocs.io/en/stable/tutorial.html#environmental-controls
                           #   * frequently used to modify ``context``
        +- steps           # step definitions, support code
                           #   * https://behave.readthedocs.io/en/stable/tutorial.html#python-step-implementations
     +- fixtures           # test data
     +- *                  # additional support files
```


Good to know
------------
* `context` provides state information to the tests; you can think of it as passing `self` to python methods.
* `context.config.userdata` contains values of defines specified on the command-line:
  ``-D NAME=VALUE`` -> ``context.config.userdata[NAME] = VALUE``
