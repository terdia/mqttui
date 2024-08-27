# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [1.3.0] - 2024-08-27
### Added
- Improved logging for MQTT connection attempts and status
- Client ID specification for MQTT connection
- Support for different MQTT protocol versions

### Changed
- Modified app.py to ensure MQTT connection is attempted when run in a container
- Refactored server startup process for better compatibility with both development and production environments

### Fixed
- Resolved issues with MQTT connection not being established
- Fixed problems related to username/password authentication for MQTT brokers
- Improved error handling for non-UTF-8 encoded MQTT messages

## [1.2.0] - 2024-08-24
### Added
  - Debug Bar feature for enhanced developer insights
  - Real-time websocket connection/disconnect status
  - MQTT connection status and last message details
  - Request duration tracking
  - Toggle functionality to show/hide the Debug Bar

## [1.0.0] - 2024-08-19
### Added
- Initial release of MQTT Web Interface
- Real-time visualization of MQTT topic hierarchy and message flow
- Ability to publish messages to MQTT topics
- Display of message statistics (connection count, topic count, message count)
- Interactive network graph showing topic relationships
- Docker support for easy deployment