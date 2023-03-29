commandline
===========


The ``osc.commandline`` module provides functionality for creating osc command-line plugins.


.. autoclass:: osc.commandline.OscCommand
   :inherited-members:
   :members:


.. autoclass:: osc.commandline.OscMainCommand
   :members: main


.. automodule:: osc.commandline
   :members: ensure_no_remaining_args,
             pop_project_package_from_args,
             pop_project_package_targetproject_targetpackage_from_args,
             pop_project_package_repository_arch_from_args,
             pop_repository_arch_from_args
