import getopt
import sys
import traceback
import configparser
import os.path
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, QDateTime, QTime, QDate, QTimer
from PyQt5.QtGui import QColor, QPalette, QFont
from PyQt5.QtWidgets import QMainWindow, QWidget, QFrame, QSlider, QHBoxLayout, QPushButton, \
    QVBoxLayout, QAction, QFileDialog, QApplication, QLabel, QComboBox
import vlc
import requests

def main():
    parseCommandLine()
    parseConfigFile()
    checkSanity()

    app = QApplication(sys.argv)
    player = Player()
    player.show()
    player.resize(600, 400)

    # cleanup
    out = s.get(
        f"{main.addr}auth.cgi?api=SYNO.API.Auth&"
        f"method=logout&version=6&account={main.username}&passwd={main.password}&session=SurveillanceStation"
    )
    print(out.json())
    sys.exit(app.exec_())


main.config = configparser.ConfigParser()

class Player(QMainWindow):
    """A simple Media Player using VLC and Qt
    """

    def __init__(self, master=None):
        QMainWindow.__init__(self, master)
        self.setWindowTitle("Summit Audio")

        # creating a basic vlc instance
        self.instance = vlc.Instance()
        # creating an empty vlc media player
        self.mediaplayer = self.instance.media_player_new()

        # empty list to store menu items
        self.itemName = ''
        self.timer = QTimer(self)
        self.timer.start(1000)

        self.createUI()
        self.isPaused = False

    # Function used for clock
    def findTime(self):
        now = QtCore.QDateTime.currentDateTimeUtc()
        now = now.toString('hh:mm:ss')
        self.clock.setText('UTC:  ' + now)

    def synologyAuth(self):
        # launch
        # Retrieve API Information
        s.get(
            f"{main.addr}entry.cgi?api=SYNO.API.Info&version=1&"
            "method=query&query=SYNO.API.Auth,SYNO.SurveillanceStation"
        )
        # login || use this one to copy & paste
        s.get(
            f"{main.addr}auth.cgi?"
            f"api=SYNO.API.Auth&method=Login&version=6&account={main.username}&passwd={main.password}&session=SurveillanceStation"
        )

        # session info
        s.get(
            f"{main.addr}entry.cgi?"
            "api=SYNO.SurveillanceStation.Info&method=GetInfo&version=1"
        )
        print('---------')
        print('auth: success')

    def getCameraId(self, number):
        # camera info
        self.synologyAuth()
        out = s.get(
            f'{main.addr}entry.cgi?version="9"&{main.survCamera}&method="List"&privCamType=1&camStm="0"'
        )
        smallList = out.json()
        camId = smallList['data']['cameras'][number]['id']
        return camId

    def getCameraName(self, number):
        # camera info
        self.synologyAuth()
        out = s.get(
            f'{main.addr}entry.cgi?version="9"&{main.survCamera}&method="List"&privCamType=1&camStm="0"'
        )
        bigList = out.json()
        bigName = bigList['data']['cameras'][number]['newName']
        return bigName


    def getLiveStream(self, number):
        # live view ****Change idList=x to the camera id number which is selected****
        self.synologyAuth()
        id = self.getCameraId(number)
        strmList = s.get(
            f'{main.addr}entry.cgi?{main.survCamera}&method="GetLiveViewPath"&version=9&idList="{id}"'
        )
        # get the rtsp link for livestreaming. Can use this rtsp link to stream the audio/video (MUST BE AUTH'D)
        strmJson = strmList.json()
        rtsp = strmJson['data'][0]['rtspPath']
        return rtsp

    def createUI(self):
        """Set up the user interface, signals & slots
        """
        self.synologyAuth()
        self.widget = QWidget(self)
        self.setCentralWidget(self.widget)

        # Clock in UTC (7/13/22)
        self.clock = QLabel()
        self.clock.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.timer.timeout.connect(self.findTime)

        # In this widget, the video will be drawn
        # Keep all OS checks for remote work
        if sys.platform == "darwin":  # for MacOS
            from PyQt5.QtWidgets import QMacCocoaViewContainer
            self.videoframe = QMacCocoaViewContainer(0)
        else:
            self.videoframe = QFrame()
        self.palette = self.videoframe.palette()
        self.palette.setColor(QPalette.Window,
                              QColor(0, 0, 0))
        self.videoframe.setPalette(self.palette)
        self.videoframe.setAutoFillBackground(True)

        # This hides the video. Needed or popup VLC will show (7/12/22)
        self.videoframe.setVisible(False)

        # Play/Stop buttons
        self.hbuttonbox = QHBoxLayout()
        self.playbutton = QPushButton("Play")
        self.hbuttonbox.addWidget(self.playbutton)
        self.playbutton.clicked.connect(self.PlayPause)

        self.stopbutton = QPushButton("Stop")
        self.hbuttonbox.addWidget(self.stopbutton)
        self.stopbutton.clicked.connect(self.Stop)

        # Volume slider
        self.hbuttonbox.addStretch(1)
        self.volumeslider = QSlider(Qt.Horizontal, self)
        self.volumeslider.setMaximum(100)
        # initial value = 0
        self.volumeslider.setTickPosition(100)
        self.volumeslider.setValue(100)
        # update value
        self.volumeslider.setValue(self.mediaplayer.audio_get_volume())
        self.volumeslider.setToolTip("Volume")
        self.hbuttonbox.addWidget(self.volumeslider)
        self.volumeslider.valueChanged.connect(self.setVolume)

        # Dropdown menu / load button
        self.topbox = QHBoxLayout()
        self.dropdown = QComboBox()
        self.loadbutton = QPushButton("Load")

        # Create menubar
        menubar = self.menuBar()
        filemenu = menubar.addMenu("&File")

        # Dynamically populate menubar
        result = s.get(
            f'{main.addr}entry.cgi?version="9"&{main.survCamera}&method="List"&privCamType=1&camStm="0"'
        )
        camList = result.json()
        camName = camList['data']['cameras']
        # magicNum = counter for cameras
        magicNum = 0
        # 0 -> 3 (7/8/2022)
        while magicNum < (len(camName)):
            string = 'cam'
            temp = magicNum
            string += str(temp)
            name = self.getCameraName(magicNum)
            self.dropdown.addItem(name)
            magicNum += 1

        self.loadbutton.clicked.connect(self.OpenFile)
        self.topbox.addWidget(self.dropdown)
        self.topbox.addWidget(self.loadbutton)

        exit = QAction("&Exit", self)
        exit.triggered.connect(sys.exit)
        filemenu.addAction(exit)

        # Display camera name
        self.camLabel = QLabel()
        self.camLabel.setFont(QFont('Times', 16))
        self.camLabel.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.timer.timeout.connect(self.updateName)
        self.camLabel.setWordWrap(True)

        # Create layout
        self.vboxlayout = QVBoxLayout()
        self.vboxlayout.addWidget(self.clock)
        self.vboxlayout.addWidget(self.camLabel)
        self.vboxlayout.addWidget(self.videoframe)
        self.vboxlayout.addLayout(self.hbuttonbox)
        self.vboxlayout.addLayout(self.topbox)
        self.widget.setLayout(self.vboxlayout)

    # Update name of camera
    def updateName(self):
        self.camLabel.setText(self.dropdown.currentText())

    def PlayPause(self):
        """Toggle play/pause status
        """
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.playbutton.setText("Play")
            self.isPaused = True
        else:
            self.mediaplayer.play()
            self.playbutton.setText("Pause")
            self.isPaused = False

    def Stop(self):
        """Stop player
        """
        self.mediaplayer.stop()
        self.playbutton.setText("Play")

    def OpenFile(self):
        num = self.dropdown.currentIndex()
        self.synologyAuth()
        self.mediaplayer.set_mrl(self.getLiveStream(num))

        # OS specific settings. Keep this for remote work
        if sys.platform.startswith('linux'):  # for Linux using the X Server
            self.mediaplayer.set_xwindow(self.videoframe.winId())
        elif sys.platform == "win32":  # for Windows
            self.mediaplayer.set_hwnd(self.videoframe.winId())
        elif sys.platform == "darwin":  # for MacOS
            self.mediaplayer.set_nsobject(int(self.videoframe.winId()))

        # Don't delete this. Automatically plays stream (7/12/22)
        self.PlayPause()

    def setVolume(self, volume):
        """Set the volume
        """
        self.mediaplayer.audio_set_volume(volume)

    def setPosition(self, position):
        """Set the position
        """
        # setting the position to where the slider was dragged
        self.mediaplayer.set_position(position / 1000.0)


def parseCommandLine():

    executable = sys.argv[0]
    arguments = sys.argv[1:]

    if len(arguments) == 0:
        help = True
    else:
        help = False

    flags = '?c:h'
    long_options = ('config=', 'help')

    options, arguments = getopt.gnu_getopt(arguments, flags, long_options)


    for option, value in options:

        if option == '-?' or option == '-h' or option == '--help':
            help = True

        elif option == '-c' or option == '--config':
            main.config_file = validateFile(value)


    if help == True:
        usage(verbose=True)
        sys.exit(0)

def usage(verbose=False):
    ''' How to invoke this program.
    '''

    output = "Usage: %s -c config_file [options]" % (sys.argv[0])

    if verbose == False:
        print(output)
        return

    output = output + ''

def parseConfigFile():

    if main.config_file is None:
        return

    main.config.read(main.config_file)
    main.username = main.config.get('main', 'username')
    main.password = main.config.get('main', 'password')
    main.survCamera = main.config.get('main', 'survCamera')
    main.addr = main.config.get('main', 'addr')



def checkSanity():
    ''' Raise exceptions if something is wrong with the runtime
        configuration, as specified by the configuration file and
        on the command line.
    '''

    if main.config_file is None:
        sys.stderr.write("Warning, no configuration file specified.\n")

    sections = ('main')

    for section in sections:

        if main.config.has_section(section):
            pass


def validateFile(filename):

    if os.path.isabs(filename):
        pass
    else:
        filename = os.path.abspath(filename)

    if os.path.isfile(filename):
        pass
    else:
        raise ValueError("file does not exist: '%s'" % (filename))

    return filename


def formatException(*exception):

    trace = traceback.format_exception(*exception)
    trace = ''.join(trace)
    trace = trace.rstrip()
    trace = trace.replace('\n', '\\n')

    return trace

if __name__ == "__main__":
    s = requests.Session()
    main()
