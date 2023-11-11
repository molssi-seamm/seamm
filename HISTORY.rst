=======
History
=======
2023.11.7 -- Bugfix: initialization of Dashboard
    * Fixed a crash that occurred the very first time submitting to the Dashboard.

2023.10.30 -- Extending and cleaning up handling of configurations
    * Added ability to name systems and configurations with the IUPAC name, InChI, or
      InChIKey of the configuration.
    * Generally cleanedup and streamlined the code handling new systems and
      configurations.

2023.9.26.1 -- Bugfix: system naming
    * Fixed a bug with keeping the current name when updating a system.
      
2023.9.26 -- Added units to header in tables, and bugfixes.
    * The headers for table columns now include units when generated automatically when
      writing results. Existing columns are not changed.
    * Changed the join step image and added the code to enable deleting it.
    * Fixed an issue with the sizie of subwindows in edit dialogs
      
2023.8.30 -- Added support for keyed columns in table output
    * Caught errors when writing out the final structures for viewing and improved
      messages in such cases.
    * Keyed columns in table output are used for e.g. the diffusion coefficients of
      multi-component fluids, where the column is expanded for each component.
      
2023.7.10 -- Adding JSON for properties in the database and tabels; bugfixes
    * Handle non-scalar results using JSON so they can be output to tables
      and added to the properties in the database.
    * Fixed error submitting jobs to Dashboard the user doesn't have a login for.
    * Ask for credentials when adding a new dashboard to job dialog.
    * Fixed bug creating a new project.

2023.6.28 -- Improved error handling contacting Dashboards.
    * Trap and display errors when contacting Dashboards
    * Allow SEAMM to continue despite such errors
      
2023.5.29 -- Fixed bug with missing directories when executing codes

2023.4.24 -- Enhancements for thermal conductivity
    * Enhanced handling of command-line options to supported self contained flowcharts.
    * Various enhancements to graphs to better present results.
    * Added tracebacks to error report to identify the code responsible for the issue.
    * Correctly remember the filename for flowcharts opened from disk.

2023.4.6 -- Bugfix: issue running standalone
    * When a description was not provided in either the command-line or the flowchart,
      running standlone crashed.
      
2023.3.31 -- Bugfix: formatting of dates
    * Fixed a minor issue with formatting the dates in Job.out.
      
2023.3.23 -- Updates for new JobServer
    * Jobs running from the JobServer now update their status in the datastore as they
      finish. This helps support jobs continuing if the JobServer crashes or stops.

2023.3.8 -- Fixed bug running from command-line (Incorrectly labeled 2023.4.8!)
    * Fixed bug running from the command-line when giving project so the job is put in
      the datastore.
    * Improved handling of title and description both when running from the
      command-line and GUI, defaulting to the title and description of the flowchart. 

2023.2.15 --
    * Improved handling of structures
    * Added ability to run simulations engine in a given directory, typically the step
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