# Changelog

## [2.0.2] - 2018-08-07

### Fixed

* GameReporterPlugins now report during gameplay even if send_begin is off.

## [2.0.1] - 2018-08-07

### Fixed

* The add game list now populates correctly.

## [2.0.0] - 2018-07-30

### Added

* Plugins settings may now be configured in-app by clicking the 'Settings'
    button.

## [1.2.4] - 2018-07-28

### Fixed

* Beginning manual sessions of games that have previous manual sessions now
    works as expected.

## [1.2.3] - 2018-07-28

### Changed

* Now a game can be selected in the "Add Time" and "Begin Manual Session"
    windows using the keyboard.

## [1.2.2] - 2018-07-25

### Added

* Now settings can be stored in the database.
* Now the windows will remember their positions.

### Fixed

* The default interval for GameReporter plugins has been corrected to one hour
    from thirty minutes.
* Closing the manual session window now correctly ends the session.

### Changed

* Commit sessions no matter how long they are.

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

[Unreleased]: https://github.com/sopoforic/gamest/compare/v2.0.2...HEAD
[2.0.2]: https://github.com/sopoforic/gamest/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/sopoforic/gamest/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/sopoforic/gamest/compare/v1.2.4...v2.0.0
[1.2.4]: https://github.com/sopoforic/gamest/compare/v1.2.3...v1.2.4
[1.2.3]: https://github.com/sopoforic/gamest/compare/v1.2.2...v1.2.3
[1.2.2]: https://github.com/sopoforic/gamest/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/sopoforic/gamest/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/sopoforic/gamest/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/sopoforic/gamest/compare/v1.0.11...v1.1.0
[1.0.11]: https://github.com/sopoforic/gamest/compare/v1.0.10...v1.0.11
[1.0.10]: https://github.com/sopoforic/gamest/compare/v1.0.9...v1.0.10
[1.0.9]: https://github.com/sopoforic/gamest/compare/v1.0.8...v1.0.9
[1.0.8]: https://github.com/sopoforic/gamest/compare/v1.0.7...v1.0.8
[1.0.7]: https://github.com/sopoforic/gamest/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/sopoforic/gamest/compare/v1.0.5...v1.0.6
[1.0.5]: https://github.com/sopoforic/gamest/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/sopoforic/gamest/compare/v1.0.3...v1.0.4
