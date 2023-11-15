Extending osc with plugins
==========================


.. note::
    New in osc 1.1.0

.. warning::
    Plugins are currently NOT supported in virtualenv.


This is a simple tutorial.
More details can be found in the :py:class:`osc.commandline.OscCommand` reference.


Steps
-----
1. First, we choose a location where to put the plugin

  .. include:: plugin_locations.rst

2. Then we pick a file name

  - The file should contain a single command and its name should correspond with the command name.
  - The file name should be prefixed with parent command(s) (only if applicable).
  - Example: Adding ``list`` subcommand to ``osc request`` -> ``request_list.py``.

3. And then we write a class that inherits from :py:class:`osc.commandline.OscCommand` and implements our command.

  - The class name should also correspond with the command name incl. the parent prefix.
  - Examples follow...




A simple command
----------------

``simple.py``

    .. literalinclude:: simple.py


Command with subcommands
------------------------

``request.py``

    .. literalinclude:: request.py

``request_list.py``

    .. literalinclude:: request_list.py

``request_accept.py``

    .. literalinclude:: request_accept.py
