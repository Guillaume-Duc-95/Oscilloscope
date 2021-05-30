
from PyQt5 import QtWidgets
from PyQt5.QtCore import QTimer, QObject, QThread
import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
import serial
from pathlib import Path
from collections import deque
import json
from pathlib import Path

from oscilloscope_gui import Ui_MainWindow


verbose = False


class SerialWorker(QObject):
    def __init__(self, numLines=1, dataNumBytes=1):
        super(SerialWorker, self).__init__()
        self.numLines = numLines
        self.dataNumBytes = dataNumBytes
        self.rawData = deque(maxlen=25)
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
            print(e)
            self.connected = False

    def listen(self):
        new_val = [0] * self.numLines
        while (self.connected):
            a = int.from_bytes(self.serialConnection.read(1), 'little')
            while a != 168:
                a = int.from_bytes(self.serialConnection.read(1), 'little')

            for i in range(self.numLines):
                new_val[i] = int.from_bytes(self.serialConnection.read(
                                            self.dataNumBytes), 'little',
                                            signed=True)
            self.rawData.append(new_val.copy())
            if verbose:
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
                line.set_ydata(a[:, k])
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
        self.ui.comboBoxPort.activated.connect(self.updateComboBoxPort)
        self.ui.actionSave_config.triggered.connect(self.saveConfig)
        self.ui.actionLoad_config.triggered.connect(self.loadConfig)
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
        # Disable inputs when connecting
        self.setStateInputs(False)

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
        # disable the input change when acquiring
        self.setStateInputs(not self.oscilloscope.acquire)

    def updateComboBoxPort(self):
        """Udpate the comboBox with the serial port available"""
        listOfPort = findSerialPort()
        # Update the available Serial Port if not empty
        if listOfPort:
            self.ui.comboBoxPort.clear()
            self.ui.comboBoxPort.insertItems(len(listOfPort), listOfPort)

    def setStateInputs(self, state):
        """Disable the comboBoxes and spinBoxes"""
        self.ui.comboBoxBaud.setEnabled(state)
        self.ui.comboBoxPort.setEnabled(state)

        self.ui.spinBoxDataSize.setEnabled(state)
        self.ui.spinBoxNumberLines.setEnabled(state)
        self.ui.spinBoxYMax.setEnabled(state)
        self.ui.spinBoxYMin.setEnabled(state)

    def saveConfig(self):
        """Save the current inputs (except Port) in a json file"""
        # Create a dialog Window to select the config file
        dialogWindow = QtWidgets.QFileDialog(self.MainWindow)
        fileName = dialogWindow.getSaveFileName(self.MainWindow, "Save Config",
                                                str(Path()),
                                                "Configuration File (*.json)")
        # Open the config file and set it in the main window
        if verbose:
            print("Save config file under:"+str(fileName[0]))

        dict_ = dict()
        dict_["baudRate"] = int(self.ui.comboBoxBaud.currentText())

        dict_["dataSize"] = self.ui.spinBoxDataSize.value()
        dict_["numLines"] = self.ui.spinBoxNumberLines.value()

        dict_["ymin"] = self.ui.spinBoxYMin.value()
        dict_["ymax"] = self.ui.spinBoxYMax.value()

        if fileName[0]:
            fileName = Path(fileName[0])
            print(fileName.suffix)
            # Check if .json extension is already persent at the end
            if fileName.suffix != '.json':
                fileName = fileName.parent / (fileName.name + '.json')

        with open(fileName, "w") as file_:
            json.dump(dict_, fp=file_, indent=4)

    def loadConfig(self):
        """Load the inputs from a given json file"""
        # Create a dialog Window to select the config file
        dialogWindow = QtWidgets.QFileDialog(self.MainWindow)
        filename = dialogWindow.getOpenFileName(self.MainWindow, "Load Config",
                                                str(Path()),
                                                "Configuration File (*.json)")
        # Open the config file and set it in the main window
        if verbose:
            print("Open config file:"+str(filename[0]))
        if filename[0]:
            with open(Path(filename[0])) as file_:
                dict_ = json.load(file_)
        self.ui.comboBoxBaud.setCurrentText(str(dict_["baudRate"]))

        self.ui.spinBoxDataSize.setValue(dict_["dataSize"])
        self.ui.spinBoxNumberLines.setValue(dict_["numLines"])

        self.ui.spinBoxYMin.setValue(dict_["ymin"])
        self.ui.spinBoxYMax.setValue(dict_["ymax"])


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
