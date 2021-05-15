from oscilloscopeV2 import OscilloscopeWindow


if __name__ == '__main__':
    oscilloscope = OscilloscopeWindow()
    oscilloscope.setup()
    oscilloscope.display()
    oscilloscope.run()
