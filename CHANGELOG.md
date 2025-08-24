# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [1.3.2] - 2025-08-24
### Added
- **Complete UI Redesign**: Collapsible sidebar layout for maximum screen real estate utilization
- **Advanced Search Panel**: Comprehensive message filtering with regex patterns, JSON path queries, content search, and time-based filters
- **Message Persistence**: SQLite database storage with automatic cleanup and configurable message limits
- **Filter Presets**: Save and load frequently used search filter combinations
- **Network Visualization Enhancements**: 
  - Node pinning functionality (double-click to pin/unpin nodes, red color indicates pinned)
  - Improved physics engine with overlap prevention
  - Fullscreen support for Message Flow diagram
  - Right-click context menu for node management
- **Collapsible Sidebar**: Hide/show controls panel to maximize Message Flow and Messages viewing area
- **Enhanced API Endpoints**: 
  - `/api/messages` with advanced filtering support
  - `/api/topics` with statistics
  - `/api/filter-presets` for preset management

### Changed
- **Layout Architecture**: Complete redesign from grid-based to flexbox sidebar layout
- **Message Flow Area**: Now takes up significantly more screen space (up to 100% width when sidebar hidden)
- **Message Rate Chart**: Moved to compact sidebar position for better space utilization
- **Topic Filtering**: Now actually filters displayed messages instead of just clearing the list
- **Advanced Search**: Collapsible panel, closed by default to reduce visual clutter
- **Screen Space Optimization**: Removed unnecessary padding, maximized content area utilization

### Fixed
- **Topic Dropdown Functionality**: Fixed issue where topic selection only cleared messages instead of filtering
- **Message Stacking**: Resolved overlapping div issue in the main content area
- **Layout Responsiveness**: Proper flexbox implementation ensures consistent 50/50 split between Message Flow and Messages
- **Database Thread Safety**: Implemented thread-local connections for concurrent message storage

### Technical Improvements
- **Database Schema**: Enhanced with indexes for better query performance
- **Message Filtering**: Support for regex topic patterns, JSON path queries, and content search
- **Network Physics**: Improved node positioning with `avoidOverlap` and better stabilization
- **JavaScript Architecture**: Modular functions for filter management and UI interactions
- **CSS Layout**: Modern flexbox implementation with smooth transitions and animations

## [1.3.1] - 2024-08-24
### Added
- LOG_LEVEL environment variable support for controlling application logging verbosity (#9)
- Topic subscription filtering via MQTT_TOPICS environment variable (#6)
- Multi-architecture Docker support (AMD64, ARM64, ARMv7) with new Dockerfile.multiarch (#3)
- GitHub Actions workflow for automated multi-platform Docker builds
- Enhanced documentation for MQTT broker address format (#7)
- Proper Flask-SocketIO server startup when running app.py directly (#12)

### Fixed
- MQTT v5 connection error by adding properties parameter to on_connect callback (#8)
- Application no longer exits prematurely when run outside Docker (#12)
- Improved LOG_LEVEL validation in entrypoint.sh with gunicorn support

### Changed
- Enhanced logging configuration with better formatting and level control
- Updated README with comprehensive configuration documentation
- Improved error handling for MQTT v5 connections

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