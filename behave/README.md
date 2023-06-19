Install requirements
--------------------

On openSUSE:
```
$ zypper install osc podman python3-behave
```

On Fedora:
```
$ dnf install osc podman python3-behave
```


Build a container with OBS
--------------------------

```
$ cd behave

# optional: refresh the base image
$ podman pull opensuse/leap:15.5

# build the container image
$ ./container-build.sh [--no-cache]
```

We can also use the built container outside the test suite
```
$ cd behave

# run 'obs-server' container on port 1443
$ ./container-run.sh

# shell into the started container
$ ./container-shell.sh

# stop the started container
$ podman stop|kill obs-server

# remove container image
$ podman rmi obs-server
```

Run tests
---------

Run all tests
```
$ cd behave
$ behave -Dosc=../osc-wrapper.py
```

Run selected tests
```
$ cd behave
$ behave -Dosc=../osc-wrapper.py features/<file>.feature
```

Run tests being worked on (decorated with `@wip`)
```
$ cd behave
behave -Dosc=../osc-wrapper.py --wip -k
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
