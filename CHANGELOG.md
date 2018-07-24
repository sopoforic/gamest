# Changelog

## [1.2.1] - 2018-07-24

### Added

* GameReporter plugins now accept `send_begin` and `send_end` options to decide
    whether to send a report when the game begins or ends.
* The main window now displays the running UserApp ID, which may be used in
    plugin configuration.
* GameReporter plugins can now accept multiple UserApp IDs.

### Fixed

* Saving an HTML report now prompts the user for a location, rather than placing
    the report in the working directory.

## [1.2.0] - 2018-07-24

### Added

* Added session status updates. By default, game reporter plugins will add their
    periodic updates to the database, and HTML reports will include them with
    the session notes.

## [1.1.0] - 2018-07-24

### Changed

* Sample configs are now written when the plugin is first detected, rather than
    when it is first activated.

## [1.0.11] - 2018-07-23

### Fixed

* Fixed missing imports that caused breakage when configs did not exist.

## [1.0.10] - 2018-07-23 [YANKED]

## [1.0.9] - 2018-07-23 [YANKED]

### Fixed

* Plugins no longer bind to events when they are not fully initialized.

## [1.0.8] - 2018-07-23 [YANKED]

### Fixed

* Events no longer get ignored when multiple plugins are installed. This was due
    to confusing documentation on Tk's unbind method. The relevant python bug is
    <https://bugs.python.org/issue31485>.

## [1.0.7] - 2018-07-22 [YANKED]

### Changed

* Improvements to logging and configuration handling.

## [1.0.6] - 2018-07-22

### Changed

* Now plugins each have their own config files. If available, a sample config
    file will be written for each plugin.
* The session notifier now accepts a `send_end` option to control when to send
    a notification when a game session ends.

## [1.0.5] - 2018-07-22

### Added

* Usage instructions added to readme.

### Changed

* Log to a subdirectory, rather than the main data directory.

## [1.0.4] - 2018-07-22

### Fixed

* The gamest_plugins namespace package should work properly, now.
* Restarting as administrator should work correctly, now.
