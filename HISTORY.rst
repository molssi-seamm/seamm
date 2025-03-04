=======
History
=======
2025.3.4 -- Bugfix: Creating a new configurarion ignored discard structure
    * Fixed the code to create new structures, which did not correctly handle the
      standard "Discard the structure" option.
    * Improved the output when discarding the structure.
      
2025.2.24 -- Changed option to "Discard the structure"
    * Changed the standard option to "Discard the structure" to indicate that the
      structure should not be saved in the database.
      
2025.2.23 -- Added isomeric SMILES to structure names and ability to discard
    * Added ability to ignore or discard a structure from e.g. optimization
    * Added isomeric SMILES to the possible names for systems and configurations
      
2024.12.7 -- Bugfix: Incorrect handling of JSON properties
    * Any properties that were not a scalar had an issue when being transformed to and
      from JSON. This is now fixed.
    * Truncated values with known units reasonablt so that they are more readable in
      tables. For example, 1.23400000001 kJ/mol is now 1.234 kJ/mol.
      
2024.11.29 -- Chemical formulas option for system names, cleaner tables.
    * Added chemical formula to possible names for systems and configurations.
    * Truncated results put in tables, based on units, to make more readable.
      
2024.11.3 -- Bugfix: removed debug printing in the flowchart
    * Removed debug printing that was accidentally left in the flowchart code.
      
2024.11.1 -- Enhancement: subflowcharts and menus handling flowcharts
    * Added a subflowchart step to allow calling another flowchart from within a
      flowchart.
    * Added copy/cut/paste for flowcharts in the menus and shortcuts
    * Enhanced the menus and bindings for operations on flowcharts so that they act on
      the currently active flowchart or subflowchart.
      
2024.10.20 -- Improvements in opening flowcharts
    * Removed directories and files not ending in ".flow" from the list of flowcharts
      that can be opened.
    * When getting a flowchart from a previous job, the list of jobs is reversed so
      the most recent is at the top.
    * Enhanced the handling of parameters to support e.g. lists of values with the
      normal units attached. Used in e.g. thermochemistry to allow lists of temperatures
      and pressures with associated units.
	
2024.10.13 -- Bugfix: Issue changing units for some parameters
    * Fixed a problem converting e.g. E_h to kJ/mol in the GUI widgets. The problem
      occurred whenever the conversion was not direct but involved different
      quantities.
    * Internal enhancement: exposed the metadata to graphical nodes as a property.
	
2024.8.21 -- Bugfix: Error using variable in stucture handling
    * The standard structure handling widgets and methods had an error is the approach
      was a variable rather than one of the choices.
      
2024.8.17 -- Enhancements to line graphs
    * Added multiple axes to line graphs.
    * Updated to correct version of plotly. 'latest' is actually not.
      
2024.7.28 -- Updating standard parameters for systems and configurations
    * Cleaned up and add to the standard parameters used for naming system and
      configurations. 'title' refers to the title in the file, if it exists.
      
2024.7.21 -- Allows capital letters in variables and columns for results
    * Allows capital letters for the variables, column names, etc. that results are
      stored in. For example, 'T', 'P', and 'V'.
      
2024.6.27 -- Added support for using local data files.
    * Added support in the Flowchart and Node classes for using local data files for
      e.g. forcefields. This allows the user to specify a local file, which is copied to
      the working directory of the job.
    * Also added a flag to both the Flowchart and Node classes indicating that the job
      is running in the JobServer rather than command-line.
      
2024.5.27 -- Bugfix: Error saving results table.

2024.5.26 -- Bugfix: Error when clicking "Cancel" on some dialogs
    * Dialogs that have a Results tab -- mainly the computational engines -- raised an
      error if the "Cancel" button was clicked. "OK" worked. This fixes the problem.
      
2024.5.3.1 -- Bugfix: JSON in Results GUI not set correctly.

2024.5.3 -- Added the time to Results.json
    * Adding time into the Results.json file will allow ensuring that the most
      recent data is used, when there are duplicates.
      
2024.5.1 -- Added ability to store results in Results.json file
    * Added column in the results tab for saving results to JSON
    * Added separators between the columns of the results table to make clearer which
      parameters go together.
      
2024.4.22 -- Moving user preferences to ~/.seamm.d
    * To better support Docker, moving ~/.seammrc to ~/.seamm.d/seamrc

2024.1.2 -- Corrected issue with citations in development versions
    * Fixed an issue getting the date of a plug-in for development versions of the
      plug-in. This did not affect end users, but did cause issues for development.
      
2023.12.18 -- Moving execution of flowcharts to seamm-exec
    * Moved execution of flowcharts to seamm-exec to consolidate execution in one
      place. This will allow easier, faster developement for running in queues, etc.
    * Switched the dependency on PMW from CondaForge to PIP since the version on
      CondaForge is poorly maintained.
      
2023.12.12 -- Moving ~/.seammrc to ~/.seamm.d/seammrc
    * Should have no effect on users. The seammrc file will be moved automatically to
      its new location. This change is necessary to be able to run SEAMM in containers.
      
2023.11.15 -- Add boolean options when submitting jobs
    * Added boolean control parameters when submitting jobs.
    * Bugfix: The previous change to allow running "flowchart.flow" in the current
      directory caused a bug in other scenarios.
      
2023.11.12 -- Allowing running flowchart.flow in current directory
    * There was a feature which prevented running a flowchart named "flowchart.flow" in
      the current directory when running from the commandline.
      
2023.11.11 -- Incorporating changes to Zenodo
    * Zenodo updated and made small changes to their API, which required changes in
      SEAMM.
    * Consolidated all private information about the user and their keys for Zenodo in
      ~/.seammrc
      
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
