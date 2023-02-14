=======
History
=======

2023.2.15 --
    * Improved handling of structures
    * Added ability to run simulations engine in a given directory, tpyically the step
      directory. This allows users to see the outputs during the simulation rather than
      having to wait until the end.
    * Added support allowing a flowchart to be run as a sub-flowchart.
      
2022.10.23 -- Simplified plug-ins
    Better support for plug-ins and the SEAMM cookiecutter:

       * Automated most handling of results and properties, based on metadata
       * Simplified handling of sub-flowcharts.

2022.10.20 -- Properties in database
    Added support for handling properties the database.

2022.9.13 -- Bugfix: reading MOPAC .mop files
    Fixed a bug that impacted read-structure-step finding MOPAC to use as a
    helper when reading .mop files.

2022.9.8 -- Remembering location of flowcharts
    Added memory of where you were last opening flowcharts, and directories that you
    use, to make it a bit easier.
    
2022.7.25 -- DOS and Band Structure graphs
    Adding support for combined bandstructure/DOS graphs.

2022.6.9 -- Addeded --version option
    * Added a --version argument to print version and stop. by @paulsaxe in #130
    * Switched to reusable GitHub workflows (internal development improvement).

0.1.0 (2018-01-20) -- Initial Release!
    First release on PyPI.
