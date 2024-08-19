# MQTT Web Interface

## Description

MQTT Web Interface is an open-source web application that provides a real-time visualization of MQTT (Message Queuing Telemetry Transport) message flows. It allows users to monitor MQTT topics, publish messages, and view message statistics through an intuitive web interface.

## Features

- Real-time visualization of MQTT topic hierarchy and message flow
- Ability to publish messages to MQTT topics
- Display of message statistics (connection count, topic count, message count)
- Interactive network graph showing topic relationships

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/terdia/mqttui.git
   ```
2. Navigate to the project directory:
   ```
   cd mqttui
   ```
3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Set up your MQTT broker details in the environment variables or directly in the `app.py` file.
2. Run the Flask application:
   ```
   python app.py
   ```
3. Open a web browser and navigate to `http://localhost:5000` to access the interface.

## Contributing

We welcome contributions to the MQTT Web Interface project! Here's how you can contribute:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/AmazingFeature`)
3. Make your changes
4. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
5. Push to the branch (`git push origin feature/AmazingFeature`)
6. Open a Pull Request

Please make sure to update tests as appropriate and adhere to the project's coding standards.

## Issues

If you encounter any problems or have suggestions for improvements, please open an issue on the GitHub repository. When reporting issues, please provide as much detail as possible, including:

- A clear and descriptive title
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Any error messages or screenshots

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Acknowledgments

- [Flask](https://flask.palletsprojects.com/) - The web framework used
- [Socket.IO](https://socket.io/) - For real-time, bidirectional communication
- [Paho MQTT](https://www.eclipse.org/paho/) - MQTT client library
- [Vis.js](https://visjs.org/) - For network visualization
- [Chart.js](https://www.chartjs.org/) - For creating responsive charts

## Contact

Project Link: [https://github.com/terdia/mqttui](https://github.com/terdia/mqttui)

## Disclaimer

This software is provided "as is", without warranty of any kind, express or implied. Use at your own risk.