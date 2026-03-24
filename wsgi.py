from dotenv import load_dotenv
load_dotenv()

from mqttui.app import create_app
from mqttui.extensions import socketio

app = create_app()

if __name__ == '__main__':
    socketio.run(app, host=app.config['HOST'], port=app.config['PORT'], debug=app.config['DEBUG'])
