from PyQt5 import QtWidgets
from PyQt5.QtCore import QTimer, QObject, QThread
import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
import serial
from pathlib import Path
from collections import deque

from oscilloscope_gui import Ui_MainWindow


verbose = False


class SerialWorker(QObject):
    def __init__(self, numLines=1, dataNumBytes=1):
        super(SerialWorker, self).__init__()
        self.numLines = numLines
        self.dataNumBytes = dataNumBytes
        self.rawData = deque()
        self.connected = False

    def updateDataStruct(self, dataNumBytes=1, numLines=1):
        self.dataNumBytes = dataNumBytes
        self.numLines = numLines

    def connect(self, serialPort, serialBaud):
        try:
            self.serialConnection = serial.Serial(serialPort,
                                                  serialBaud, timeout=4)
            print('Connected to ' + str(serialPort) + ' at '
                  + str(serialBaud) + ' BAUD.')
            self.connected = True
        except Exception as e:
            print("Failed to connect with " + str(serialPort) + ' at '
                  + str(serialBaud) + ' BAUD.')
            self.connected = False

    def listen(self):
        new_val = [0] * self.numLines
        while (self.connected):
            a = int.from_bytes(self.serialConnection.read(1), 'little')
#            while a != 168:
#                a = int.from_bytes(self.serialConnection.read(1), 'little')
#                pass

            for i in range(self.numLines):
                new_val[i] = int.from_bytes(self.serialConnection.read(
                                            self.dataNumBytes), 'little',
                                            signed=True)
            self.rawData.append(new_val.copy())
            print(new_val)


class Oscilloscope(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.data = np.arange(25)*20-255
        self.fig = plt.Figure(figsize=(width/dpi, height/dpi), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        self.lines = None
        FigureCanvasQTAgg.__init__(self, self.fig)
        self.setParent(parent)
        self.delay = 0
        self.acquire = False
        self.worker = SerialWorker()
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.listen)

    def plot(self):
        if self.acquire:
            a = np.array(self.worker.rawData)
            for k, line in enumerate(self.lines):
                line.set_ydata(a[-25:, k])
            print(self.worker.rawData)
            self.delay += 1
            self.delay = self.delay % 5
            self.fig.canvas.draw()

    def initPlot(self, numLines, ymin, ymax):
        data = np.zeros((25, numLines))
        self.axes.set_ylim([ymin, ymax])
        self.lines = self.axes.plot(data)

    def start(self, serialPort, serialBaud, dataSize, numLines,
              ymax, ymin):
        self.worker.connect(serialPort, serialBaud)
        self.worker.updateDataStruct(dataSize, numLines)
        if self.worker.connected:
            self.initPlot(numLines, ymax, ymin)
            self.thread.start()
            self.acquire = True

    def backgroundThread(self):
        '''Defines the serial listening task'''
        new_val = [0] * self.numLines
        while (self.acquire):
            a = int.from_bytes(self.serialConnection.read(1), 'little')
            while a != 168:
                print(a)
                a = int.from_bytes(self.serialConnection.read(1), 'little')
                pass
            for i in range(self.numLines):
                new_val[i] = int.from_bytes(self.serialConnection.read(
                                            self.dataNumBytes), 'little',
                                            signed=True)
            self.rawData.append(new_val.copy())


class OscilloscopeWindow:
    """GUI interface"""
    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.app = QtWidgets.QApplication(sys.argv)
        self.MainWindow = QtWidgets.QMainWindow()
        self.MainWindow.timer = QTimer(self.MainWindow)

    def setup(self):
        """Load the ui interface"""
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self.MainWindow)
        # Set the plot part
        self.oscilloscope = Oscilloscope(self.MainWindow, width=791,
                                         height=891)
        self.oscilloscope.move(325, 11)
        self.connectSignalsSlots()
        # Update the comboBoxPort:
        self.updateComboBoxPort()

        self.MainWindow.timer.start(34)

    def connectSignalsSlots(self):
        """Link button pressed to action"""
        self.ui.pushButtonStart.clicked.connect(self.start)
        #self.ui.pushButtonStop.clicked.connect(self.stop)
        self.MainWindow.timer.timeout.connect(self.oscilloscope.plot)

    def run(self):
        """Create infinite loop and wait to operating system action"""
        sys.exit(self.app.exec_())

    def display(self):
        """Rendering"""
        self.MainWindow.show()

    def start(self):
        """Start the acquisition of serial data"""
        serialPort = self.ui.comboBoxPort.currentText()
        baudRate = int(self.ui.comboBoxBaud.currentText())

        dataSize = self.ui.spinBoxDataSize.value()
        numLines = self.ui.spinBoxNumberLines.value()

        ymin = self.ui.spinBoxYMin.value()
        ymax = self.ui.spinBoxYMax.value()
        if verbose:
            print("Baud rate:"+str(baudRate))
            print("Serial Port:"+serialPort)
        self.oscilloscope.start(serialPort, baudRate, dataSize,
                                numLines, ymin, ymax)

    def updateComboBoxPort(self):
        """Udpate the comboBox with the serial port available"""
        listOfPort = findSerialPort()
        # Update the available Serial Port if not empty
        if listOfPort:
            self.ui.comboBoxPort.clear()
            self.ui.comboBoxPort.insertItems(len(listOfPort), listOfPort)


def findSerialPort():
    """List all of the available serial port"""
    platform = sys.platform
    if platform == "linux":
        # linux
        listOfPort = list(map(str, Path("/dev").glob("ttyACM*")))
    elif platform == "darwin":
        # OS X
        raise Exception('Function not implemented for this platform')
    elif platform == "cygwin":
        # Windows
        raise Exception('Function not implemented for this platform')
    return listOfPort
