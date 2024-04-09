"""
Divoom Pixoo64 Album Art Display
--------------------------------
This functionality automatically showcases the album cover art of the currently playing track on your Divoom Pixoo64 screen.
In addition to this, it extracts useful information like the artist’s name and the predominant color from the album art. This extracted data can be leveraged for additional automation within your Home Assistant setup.

# appdaemon/apps/apps.yaml
-----
pixoo64_media_album_art:
  module: pixoo64_media_album_art
  class: Pixoo64_Media_Album_Art
  home_assistant:
    ha_url: "http://homeassistant.local:8123"  # Home Assistant URL
    media_player: "media_player.era300"        # Media player entity ID
    toggle: "input_boolean.pixoo64_album_art"  # Boolean sensor to control script execution (Optional)
    pixoo_sensor: "sensor.pixoo64_media_data"  # Sensor to store media data (Optional)
    light: False                               # RGB light entity ID (if any) (Optional)
  pixoo:
    url: "http://192.168.86.21:80/post"        # Pixoo device URL
    full_control: True                         # Control display on/off with play/pause
    contrast: True                             # Apply 50% contrast filter
    fail_txt: True                             # Show media info if image fails to load
    show_text:
      enabled: False                           # Show media info with image
      text_background: True                    # Change background of text area
      font: 2                                  # Pixoo internal font type (0-7)
      color: False                             # Use alternative font color
    crop_borders:
      enabled: True                            # Crop image borders if present
      extra: True                              # Apply enhanced border crop
"""
import re
import base64
import requests
import json
import time
import zlib
import numpy as np
import random
import traceback
from io import BytesIO
from collections import Counter
from unidecode import unidecode
from PIL import Image, UnidentifiedImageError, ImageEnhance, ImageFilter
from appdaemon.plugins.hass import hassapi as hass

NO_IMAGE = b"x\x9c\xed\xd3K\x0e\xc3 \x0c\x05\xc0#q\x86\xdc\xffR\xed\xa6RU\x81?\xd0EZ\xcdl\x92 d?\x87\xe4\xba\x00\x00\x00\x00\x00\x00\xf8W\xe3\xa9\xba>\xdetjvzD\xeb\x95\x1cc!\xab\xd5\x9d!\xab\x99\xf5\xc8\xfaV\xdfM'WT/\xaasz~\xdf\x9a\xbf\xd2\xef\xae\xf3G\xd7J\x9e\xa8_w\xcfj\x7f\xe5\xbe\xd2kw\xfe\x9d\xe7\xcf\xefh,\xccrV\xb2v\xe6\xac\xd6\x8c\xe6\x8frW\xfa\x9d\x9c\xff*\xdb]\xcf\x7f\xb6~:\xffkm7K\xb6\xb7r\xdf\xe9\xdb\xc9U\xa9\x1f\xadW\xfe\xa7,\xd3\xe9\xfcY\x8e\xd9?\xd4}'\x00\x00\x00\x00\x00\x00\x00\xbf\xe2\x01\xb1:\x16y"
TV_ICON = b'x\x9c\xed\x9a\xd9\x92\xab8\xb6\x86\x1f\x88\x0b\x06\x03\x86Ka\x063\x9aQ\x0cw\x18l\xe6\xc9\xe0\xc4\xf6\xd3\xb7\xc8\xdcU\xbdwE\xc7\xa9\x8a>]\x99\xd1\x1d\xf9G\xfe\x91\xd8\x08\x99\x0fIKK\x00\x00\xdf\xfa\xd6\xb7\xbe\xf5\xado}\xeb[\xdf\xfa\xd6\xb7\xfe\xbf\x12\x0b\xfaT\x8f\x077\xea\x84\x12\x14\xea\xe1\xaf\x1c\xa3{\xcdd\xbeL\x028\x92\xf0w\x9f\xdf\xdf-q\xe5\xec.\xb9g\x83\xae7\xbe\xf40\xd1\x9f\xffg\xc7\x94j\xaa6\xc9)\xf8\xab\xd7\xeb\xbfA\x92\xab\x06~\xabEy_\xb2\x8e$\x0b\xc2\x9a\x1d\xffU9Eh\xd2l\x07\xa9\xe3\x13\xd4\x9f}\x8e\x9f!\xf5`\xdeBJX\xd2\x90\xdc\x9b\xb5I\xfd\xb2s5\xc5(\x14:\'pO_tz\x9f&\xab6\xe3X\x91\x8b\x10.\x95\x88\xc0\xb7\xef\xd0\xb8\xaf"J\x9b\xd0\xc7\xff\xaaq\xef\xd4\x99^\xf6RT\xed\xe2\xa4\xdaeq}\xcc\xa2\xbao\xc2\xba\x1f`\xbd\x9b\x83\xe6H\xf8\xef\x8e\xc1\xa9\x89U\xa3\x8e\x81Z\xec\x02\xb5\xa6\xc1\xf9\xb5\xe7\xed\xc7\xbeM\x1b\xda\x81wv\x01\xf3\xe40\xd5q8\xa2r\xa8\xac\xe4\xbd;\xe2>\xfc\xa3\x9e\xadNTwXGMTG\xc5\xe68\x85\x8d-\xbb\x92\xf8\xd9\xec\xb9"Ab\xef\xba=\xed:\xedn<v\x11y\xec\xfa\xcd\x8c\xd2\xed6\xf32\xda~w\xaf\nRO[\xe2\xa0\xe6\xe2@/\x87q \xf0I\xa5\xb9\x91&\xf6\xe3@J#Mc\xe3\xb0\xee\x87\xa1=\xf4\x83+\xf5\xaa,u4:F\xfd\xc9GT\xdfV\xe7V\xf7\xf6\x1b\xd1Ci\xfb\xc5x\x9b\xe4\xe8\x9e\xd0\xcbg\xf3\xbft^\x0fE\x9aR\x1c\x00\x8e\xc8\xf2\xfa\x07\x17(\xa6\x81\x8f}ZQ\x00\xa3\x94\x80\xe5\x16\xe0T\xd2\xc0\xf6L\xc99\xc4\xc7\x0f\x07\x8a\xed\xa9\xe2\xf6\xbd%4\xc0p%\xa09\x19\xd8\x82\xe4o\xf5\xfc\xee\x9f\xeb\xfea}\xe5\xc2\xdb(\x7fz\xdc\xb8\x8f\xa4k\x08\x12T\x0b\x15\x18\x808x/\x15uz\x8e\x80>2\x01va`\xd2\xb1D\xb0i\x9b\xed\xb3P\x069\x95\xab\x17\xea\xe1\\wBT\xf4VV\x1e\x93k\x19\xe5e\x19\x95\xe5\xb6]D\xd6\xf9\x1a\xf2\xf0\xa2\xb4VFYJJ\x8eB\xdcpXH\xc4|\x188\x1c2\x1bJ*\r\ti\x07k\x9a8\xb9\xab\xaf\xad\xf1\xfb5\xb8\xc0\x95\xfa\xf33\xfe\x0f\xf3\'\xcb\xc9t\x9dP\x03\x81\x90\x90\x96\x9c\xb4\x9a\x8c\xceo\x176\x0e\xb2I"~\n\x9d\xf3>\x94\x12\x10J\xa5\x14\x11\xa3\x9a\x04\xa4\x91\xca\xb2\x95\xb6\x96\x9d\xb6\xae\x9a\x92\t\xe2\xcc\xd5\xcdgy\xd4\x11\xb3\x96Bt5H(\xc7\xd0\x12\xa3\x86\xc3#i\xe0B"c#)`")F\xff\xb3}\xd44X\x1e\xc2\xd8\xa9\x8a\xcb\xc6\x7f\x95\xb9\xdd\xa7\xf3\x8f\xcb\t\xb5\x7f\xe0\x89\xa0MHM\xd6\xd6B\xd1\n\x07\xf5\xf5U2=\xf5\xe2\xbc\x8a\'\x0c\x1a*\x81\xc1>k9\x0c\x86\x80wZ\x8ewC\xb0wC\x95\xf3\xa8\xbc\xf5\xc3\x91\xf6\xc3\x85\xf4\xc3\xfc\xe5\xb5V\xe7\x05d\xe9IL\x85\xf2\xa5k\x14\xe4q\x18hn \x92G\xd7\x8f\xe9\x937\x0f\xba[x\xdb\xd8\xd0\x1c\x13\xb8\xd5Zf\xa1\xe0*\xeb;\xff\xe7\xb7?\xb3\x9c\xf4\x12\xf8\xa1\xe4\xd0\xa8\xef7j\x81\xc6\xf7s\x1d/\x11\x85R\x9c\xabE\xf3\x87\xeb\xfe\xbc\x18|\xe6\xfa\xb8\xd9z\xfd\xaci\xf1\xf9!$\xfb\x95Kn+~\xc9^Za\xf9Xa]\xf9k\xb6\xa7\x92D\xb4\xa3~\x7f\x88b\xff\x98\xd2G\xf1\xd6aoKH\xcd\xb7\x10\xbb/\xfd\x94\xbf\xe2\xf1\xde\xf6B\xe5\x05\xae\xac\x97\xa6\xa9\xaf\xb3\x90A\xde\xd1@|\xb8\xb4+\xf9\xe9\xfc\xe3bo\xfc\xb0\x01\xa4W\xd1W\xbd\x9c\xe3*\xd1#\xcc\xbe\xed\xf1M\xf7p\xe2o\x8c\x88\xf8\x1d\x9c+\xed~\xcf+\xc9\xb9\xc0\xd3}\xb1G\xc6\xaef/\x15\xbc\xc8\x17\xbcM\x16\xe6mMh\\\x8fv,\x1e\r\xbexV\r0\xf7\xdd\xf3\xbe\xab\xd6\xa5\xbf\x90\x8fXo1\x8d\xa7p\x86\x7f-\xb4\xb5\xba\x92&\xa1\xb8\xa7\x9d\xdb\xd1T\xd7\x8d\x9f\xf8\x02\xfe\xf1\x83\xdf\xa7\t\xf7I\x14nc\xc9\xe4r\xcb\xf1\x1f\xc2.^\xcf\x9b\x89\xc0g\xcb\t\xe7\x18\xab\xe7d91\x10\xff\r\xf1\xdf\n\xec\xc2\xf5b\xb1 \xfe\xc5&\xaf\x1c\xe2\x1f\xfe\xc8?!\xfe\x0e\xf1W\xc4:(\xf5~\\H~\xe4i>i\x9f\x97\x10\x16\xe6AJ\xcfry\xfc\xe0\xff\x82\xf6\xd7Z[\x7fH>\x14\x89\xa7[\xabmL\xc1\x91\xb3\r\xe2w\xfe\xfb\xa5\xe3\xe7\x15\xe3y\xd9\xc4yh\xf4\x9c%\xc5\xfb\x12\xfcu\xfe\xeeW~f!9\xed\xb1\xc3G\x86\xe8v\xee`\x8b\xe6-%KY]\x03\x01\xc5\xff/\xe3\x0f^\xeb\x9b\xe7gs\xde\x8f8~\xdda\xbf\xf1\xe3\xa7{\x8bY*\x87Y\x89\x86\xf3\x8b\xdasP\xfc\xeb\xfc:\xfe\x83\xff\xf1\x07~\x1a\x9fdz\x8a\xc6\xd1E\xd7\xfd,\xb7\x12\xe2?|\r\x7fi\xa3\xf8\x8f\xfa?\xb1\xf8>\xf1V\xa8\xa1\x86\xff\xac\xd3\xb3\xc6\xac\x86\xe1\xf9\x87\x82c(\x7f\xe3\x92C\xbc\xcf\xff=~Zi\xf6\x0cCs\x1aI\xe3Zy\x9f\xa3\xa4\xf1\x02gw\x86\xa3\xa8\x16[\xfb\xcf\x9f\x1e\xff\x17&\xb7QN\x87\xe2?\x98\x83@}\x96jw\xfa\x95\x1f+\xb1\x9c&\xb0\x8b&\xe0\x18\x04=W\n\xef\xfc\xfb\x1f\xfc\xf3\x9f\xf0\xef\xa6\xe7[\xf4|\xde\x8fw\n\xf1\xa3\xf1o-\xfb\xd8\xbd`\xd1\xc3Y\x8eB\xe67\x03\x7f\x86\x0b\xe2w\xbe\x86\x7fL\x1c\xb3\x0c|\x94\xefL\x01\x11\xbf\xca\xe1\xee\xfc\xc2o\xeb\x08R}b\x17\x17\xe0X\x8c\xf7\\\x0b~i\xff\x0c\xf1\xe7\xef\xfc\x14\x8a\xffo\xa9&\x1aq|\x14\xe2\xb8W\xce\xf4\xf50\xef6\xf6\xd3}\xa2\xbae\xa6B\x97\r\x99#\xdb12\xbf\xcb\x8dE\xe1\xcf\x81\xf48\x9c\xdbw~\xf0%\xfc\tt\xac\xb2\xf1\xa3 \x9e`\xd3\x10e\xdc\xd9\x98}e0\xbb\xa61\xfc\x8d\xc70\xec\xfa\xc1\x1f\xa3`8`\x03\xf7@\xec%\xc8n\xcd>;7X1\xbfI\x15o\xf0\xd5\x12Qh{M\xe2\x97\x1aF!\x03\x8f\x1e\x1dR\xd5\xbd\x97\xabb\x08\xb0\xb4\x93\xee\xf9\x04O2C\x95\x80\xedH\x85\xdfAm\xa6\x1eq\xd0\xf0\xf2\x99\\$\xb50\xc1E\xfe\x02~\xcduN.\x8d\xf8\xb3)\x94\xd6\xdd\xd6\xff\xf7\x97\xd7\x9d\xb9\x9f{\xe6^\xbf\xed-/\xe7g\x0b\xcd\x7f\xa5\x81s\x0f\xfd\xba\xcf%3}\x08\xa7\x89\xe0O\xe9\x8a\x9f\xf6\x1d~:\xe3;#;\xae\xda\xcd\xeeN\x10\x9blB\x89N\xd2%s\x83KZ\x13\x1e\xec\x88K\xd8I]>\xb5\xba\xcc*1\xce\x86\xad\xc8\xefde\xee\xc6\x10BMC\xfc\xa2\x8ar\xc1\x0b\x1c\xbe\x86\xbf\x02~\xd4dc\xd8\x10\xcc;\xffi7\xd3\x98\xdf\xd0\x97\xe8\xc6\x9aT\xc6\x1b\xae\xca\xdd\xa0\x8f\xef\xad J\xa1\x064F\x00\x1a\x81\x01\r\x85k\xbdc\x81\xbe_\x81a\xdf\x04\xbd.\r\xa8\xd7\xb6XyV\xe3%n\x13&\x88?\xdc\xf8\xdb\xa6B\xed\xaf\xa0\xf6w86\xcc\x01\xdf1\xd2\x1c\xb6\x10\xb6\xd0<\x93\x8f\x0f~\xf9\xf3\xf9g\x06\xf1?\xc1\xd6\xff\x87\x90\xa0\xd9\x82\xae,\x16{\xbb\xd1\x98\xdd\xd0\'\x7fb\xb8\xe7\xf9\x83\x1f\xe5\xbf{\xcd\x8fX\xa8\xbf\xf3\'4\x06\x12\xc4\x9f"~CD\xfc\xfeM\x98\xea\xcah\x0f\xf5\xa9N]\xabQ\x12W\xf2\xe2\xba\xd1a\xd7\x9c`\x1b\xa4\xe7I\xc2D\x86\x92XV\t0\xbe{\x08s\x97\xfb!\xccO\xbf\xb7\xbf<|\xfa\xfagf,\xe7Tr~$9]$q\xfb+\xedi\xec\xa9\x1e\xe9\xbbQ\xef0{d\xe6\xe9\xcc\xedQ\x02p\xd3\x10\xbf\x80\xda\xdfE\xfc$j\xff\x15\xf1?\x00\x98*\xd4\xfe;\xc4o \xfek\xa1\x13Xu\xf2=\xdb\x12\xb1\xc8i\xf4\xa8\x0e\x0eA\x17(\xb0\x95\xbc\xf3HP"C\xd24\x1b\x9a<\xdf\r\xf8\x8d\x82nH\xb6\xce;?P\xbf\x86?\x91\xdd\x93@\xf8a 5h\x9d\xca\xe4\xc7\x11\xa3/FM\xdf\xedzw?\xf6L\xd6\xa5\xdc^V\xb9\xb3\xe0\xe3,\x19\x84\xac\x86\xf8\x1f\x1b?\x0f\x92\x01\x03S\xca\x00\xfd\xf5\x86\xfa\xc0$LQ\xa1KTa\xd5\xfa\xc9\xac\x9f\xd0\xa91X\xbd(\xaf}\xa1\xc1\xd4\xe8\xe9\xd8\xdc\x0f\x0cI\xec\xd8P\xda\xf3]\x83\r\x94\xe6\x85\xe4\xe8\x9e\xdbVP\x81\xf4E\xfc\x82k\xb9\xcd\x96\xffTq\xc0\x91q\x97\x0c\x04\x1f\xc5\xcc=\xea(\x1e\xef\x18\xb3Jx\x9dW\xb9\x94G\xfc\x0f\x18\xb2\xf2\x0f\xfe\x19\xf178\x98B\xc4\x7f{\x03:>\t\xa9_j\xc4t5\x9f\x98e\x8aw\xe8\x88,\xac\xea\xa7\xd7\xd6,\xe2W\x921\x98\x04\xa6\x9d)\xb6\xe5\x18\xbe\xcb\xb8\xbae`\x04\x1f\xce\xb9-\xf0/k\x7fMp\xcd2\x0e\x02\xbf(R\xe8\x90\x81\xc4[\xe3D\x11h\x0eX\xe8{tc\xe6.\xe5o\x02\xe2g\x10\xff\x82\xf8\x05\xc4\xbf\xfc\xc4\xef!\xfe\xfe\x8eb\xe0(Lv\xa95\xd5\xc5\xf4X\xc3xM\x81#R\x1f\xfc/\xcao\x82C26\x9d\xc0\xb6\x03\x81\x85\x80\xdc\x85\xae\x90\xb4\xe39\x85\xbcy\x86\x19\xf6\xa5\xfc\x82\x19\xf8\xa2z9\xb7\x19\x15\x12+\x13\x85\xd68\xb2,IZ\xb7\x865\xa7\x0c?[*nl\xf1O\x80(\xfe\xab@\x07<\xd08\x16\xcd\x01\x1c\x8a\xff8bgP\xfc#@ZO*\x11VF\xd5\xd9\xfa+\x8dl\xbf\x8b\xeb\xba\x82\xdd\xab\x0b\xdb\x9a\xca\xa7\xe0"\xb2m\xf1"\xc8\x95\xbf\x90c\x18\xb6Lz\t\x13\xed,\xc7\xfc\xd6\xffs\xb2\xf9\x8a\xfe\xef\x19\x0f3@k\xdf\x0c\xf5C\xe6,\x9bD\x02\x93C\x88&\xa6,\xca\xf7\x15\xed\x92=m\x85\x13\xdd\xa6o\xea\x12\x07\x03JbTM\x91h\xf9 \xf5\x8c(\xc5\x97\xb3\xa4\xde\x80H\xb3{\x89\x0e\t=\xf0d\xd3\xd7h\xe3\xb5\xe0\xb6H\x81\xacf\xf0K \xe3\x19\x91\xe39)\xace\xbbx\xa9"\\\xd18+\xae!\x19\\\xc3\xd2H\xdb`\x7f\\\xc1\x97\xf0\xdfh\xc6C\xf9/4\x1e\xb1u\x86\r\x97\xc1f\x7f\t\xe5\xc3U)\xcd\x8bR\xba9\xc5\x14\xf9\xce\xbd_v#Q\xa8\x02[\x0e\x1e\xa8\xd4J\xa9h\xca\xa8G\xc5\xad\x990j\x92.k\x98g\xd9jl\xd30\xf7\xa2I\xaas=\x9e`\xad)vE\xb3z\xa5NRI\x97|\x19\'t\x11C\xbaR\xb5\xb7\xe6H\xd6\xe5N\x8b\x8a\xf0\xe1\x04>1o\xf7\x89Q\xfe\xcb|:\xff@z\x96[\x84\xdb\xfckW(\xfd%\x01\x9b\xb6\t\xd8\xd6\xa4\x99\xcc\x1c3J6\xf2\xd0u\xf2\xae\x0crjL\xae\x14\x7f)z\xb9,{\xd8W\xc7\xf6V\xf5\xcb\\G(S\x1c\x84g=\xc8D\x1d[D5\xc8\x8f\xea\xc8\xcce\xff\x18\x8b\xa8l\xae;\xb7\xb8\xf6rvU\xc8\xf8\xd2\xb5A\x1eZV\x06y\x94\xf7\x91J@8\x84^\x9a\xfa\xd6\xfeh\xfc\x7f\x01\xff\xe3\x9d_s\x024\xacWQw\x0b\xcb\xf4T\xcf\xf2\x82\xf8t\x18.\xf6\x81(\xed\x1a4\x8eo\x0e\xce+\x9e]\xbf\xb9\xbbu\xf3\xe6\xbe\xe6\x87\'\xae\xaf\x1f~~x~\xba\xafau\xeb\xe2\xcd\x15\xb3\xc5y\x057\xc7W{t|}z\x12\x85\xf5\xccR\xa3\\-C l\xad\x0c,\xd5\xa1\x8f\x9aC+\xba3\x83\x1f\xf3\xdf\xe7\xf3\xab\xff\xe47\xc0*\x18\x05\x07\xec\x03\x10\xfc:>\x85DP\xa52xdp\xc6/Tn\x16\n\x03\xcb\xc8=\xa3\xf6\xee\x9b\x01\xde\x9b\xc1}k\xe3\x9c\xe8\xd4e\xd7\xc6%\xd1\xd0\xee[C\xc3\xb7\xbag\x06T.+\xb6\xe7\x00Tne-\tR(=aM$Y(\xab-\xa3+U,\xb3\xde\x81\x9b\xb7{\xcd\xfa\xba\x82\xe3\xba\xf17\x9f\xce?\xd1\xe3O\xfc\x84\xb0\xdd\x8f5J\x00lO=\xf8\xbec\xa2\xbc\xe8\x12\x13\xeb\x92\x92\x01}\xe9\x00VR\x0f\xa9\xe8\x1eV\xa9\xf0~}\x94\x8d\xfahy\xd51\xc9\xab\x9df\xd7\x91v*vBPP\x0f\xb3R\x1e\xd2\x85\x920\x14\xdb\x99D"\xde\xa08\xc0\x146\xfc\x9bq\'GF~\xdc\x98e\x7f\xd3\xc3\xb3s\x08\x8a\xed\xf9\xc76\xff\xa1\xf8\xf7\x05\xfc\xed/\xfc\xbf_\x83\x95\x13N\x0fN\xf0<N\x0b\xfc!\x8c\x02\xf3\xda\x1e[\x88\x16\xf2Q\xdd[\xf6\xb5\x03\xfb%\r\xcdQ\x13\x9e\xdb}\xdbq\x14\xd6\x99\xf5\xcc\xab\xcc\xd1\xf5\xce\xdd\x16\xfcQ\xd3\x97A\xd8\xa8%\xca\xadb\xfb\xa9\x82j\xd0v7m\xc1k% \xbb\x9e\x8c\x16=5R\xb245`~\x1d\x7f\\z\xe6#\x0b~\xe6\xff\xf0\xfbX\x10\xac\xc7 8\x87X\xf4E\xe9X)\xe4\x111[\x17E\x00g(\xdd\xe7\xe9 \xb6\xaa\xd0&R\xd3\x0fj\xdbOI\x05\x12i\x98\x8a.\x17\x97)\xb4\xaeT~t+Zw\xbdABu\x82L\xb1\xae\xf3\x14\x1a\xfd\x00\xcb\x99\x9d\x92y\xf2N11\xb3\x1a\x08\xc0\xfb\xfc\'g\xf4g\xf3\xcf\xa3\x10\x9d\x04:\xdf\x9e?\xa9\xab\xf3\xab\x0b\xd4.\xab\x89R\xfd\x06\x18\x0f\x07\xc5\x05\xf5\xe0z\x84\xedx\x83\xe1\x8b\x8e\xe7\xbf\xe2\xd0\x13U\xe8\xbf\x8a4\xa8\x8b\xc4\xf3\xd5\xd0\xf58\xb4\x03X(\x9fp\xac\x92\x10M\x01\x8do0\xa0\xd6EKe\x14\xea\xabA`\x86\xc4\xc5\x86\xd1\xc5\xcb\xc8\xaa\xd0u\x91\xb7g\xab\xef\xcf\xbf(\xed\xd3\xdf\x1b\xe8\xfaa_\x85$:\xdf\xb5\xf1\xbc\xb5\xf80Q\xf8\x07\xae\xdc\xb6\xdd\xe7\x8c<\x14\xdea.\xbc\'w\xf5_(e\x11\xe9+\xea\xd7\x15Z3V\xb1T\xb4\xc8]Ddm\x14\x04u\x148\x15\xac\xd7\xf7r\xde\x0b\\\xbd\xc3\xf0\xfb\xf1\xce3F\xdf\xab\xf5Eq\xdd\x8bbY\x81\x1f4\xae\x97]\x9dgV\xa2>\xc4.\xa3\x15~6\xbf\xf6X\xb5\xaa\x9b\x9f7u\xb4\xee\x89\x1b\xdc\xc7$\xba\x8f\x10\xde\x13\xe8\xddh\x94\x01\xc7\xa3q\x8b\x1f\xe6\x87\x17\xf36l~l6P\xeed\xdc\x86\x1f\xa6\x7f3i\xbc\xef\x1b~+\xbf\x95%\xdf\x8f\x9fU\xd2\xbck\x96=\xc7\xa3v\xa3[}\x19e\x17\xd5\x87~c9\r\x83,B\x91\x8b?\x9b\x7f\xd3a-\x0e\x9a\xbb\xea\xfekH\x1aj\x9e*\x05\x14v\xb5\xfaFeZ\xba\xc0\x19\xff4\xad#k\xda\xe3\xff\xf6V\xe6Ws\xfa\xfb\xf1.g\x98\xcf\xd8+\x15\xf5\xd6\x1f\xd5[\xd2\x14)\xfalo\xfb\x14\xd7T\xbe\x82\xfdg\x89ksL\x1a\xd3\x0fD\xc7?8\xb1\xfa\xb7\xfc\xc8*\x89\xb6\xd7\xc0\xac!"\xed1X\x7f\xcbo\xfc\xbb*$Avh])\xd5\x93\x00\xcc\x7f\xfd.\xce\xf6N\xdfj\x8a\xdb\xfbo\x87b\xd0\xb7w\x9fD\x87\xb0\xb6\xf7$\xdf\xff\xa3\xcf\x07TH\x00\x8e\xf4^\xf6\x8f\xef@:@\x90V\xc28\n\x8e%\x14\xce\xa7\xbf\xef\xf3\xado}\xeb[\xdf\xfa\xd6\xb7\xbe\xf5\xado\xfd/\xe8\x1fi\xe3\xba\xee'
BLK_SCR = b'x\x9c\xed\xc11\x01\x00\x00\x00\xc2\xa0l\xeb_\xca\x18>@\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00o\x03\xda:@\xf1'
# ---------------
IMAGE_SIZE = 64
LOWER_PART_CROP = (3, int((IMAGE_SIZE/4)*3), IMAGE_SIZE-3, IMAGE_SIZE-3)
FULL_IMG = (0, IMAGE_SIZE, IMAGE_SIZE, IMAGE_SIZE)
HEADERS = {"Content-Type": "application/json; charset=utf-8"}

class Pixoo64_Media_Album_Art(hass.Hass):
    def initialize(self):
        home_assistant_args = self.args.get('home_assistant', {})
        self.MEDIA_PLAYER = home_assistant_args.get("media_player", "media_player.era300")
        self.TOGGLE = home_assistant_args.get("toggle", "input_boolean.pixoo64_album_art")
        self.HA_URL = home_assistant_args.get("ha_url", "http://homeassistant.local:8123")
        self.SENSOR = home_assistant_args.get("pixoo_sensor", "sensor.pixoo64_media_data")
        self.LIGHT = home_assistant_args.get("light", None)

        pixoo_args = self.args.get('pixoo', {})
        self.URL = pixoo_args.get("url", "192.168.86.21:80/post")
        self.FULL_CONTROL = pixoo_args.get("full_control", True)
        self.FAIL_TXT = pixoo_args.get("fail_txt", True)
        self.CONTRAST = pixoo_args.get("contrast", False)

        show_text_args = pixoo_args.get('show_text', {})
        self.SHOW_TEXT = show_text_args.get("enabled", False)
        self.FONT = show_text_args.get("font", 2)
        self.FONT_C = show_text_args.get("color", True)
        self.TEXT_BG = show_text_args.get("text_background", True)
    
        crop_borders_args = pixoo_args.get('crop_borders', {})
        self.CROP_BORDERS = crop_borders_args.get("enabled", True)
        self.CROP_EXTRA = crop_borders_args.get("extra", True)
        
        self.FALLBACK = False
        self.album_name = self.get_state(self.MEDIA_PLAYER, attribute="media_album_name")
        self.listen_state(self.update_attributes, self.MEDIA_PLAYER, attribute='media_title')
        self.listen_state(self.update_attributes, self.MEDIA_PLAYER)
        
    def update_attributes(self, entity, attribute, old, new, kwargs):
        try:
            input_boolean = self.get_state(self.TOGGLE)
        
        except Exception as e:
            self.log(f"Error getting state for {self.TOGGLE}: {e}. Please create it in HA configuration.yaml")
            self.set_state(self.TOGGLE, state="on", attributes={"friendly_name": "Pixoo64 Album Art"})
            input_boolean = "on"
        
        media_state = self.get_state(self.MEDIA_PLAYER)
        if media_state in ["off", "idle", "pause"]:
            self.set_state(self.SENSOR, state="off")
            self.album_name = "media player is not playing - removing the album name"
        
        if input_boolean == "on":
            self.pixoo_run(media_state)

    def pixoo_run(self, media_state):
        payload = '{ "Command" : "Channel/GetIndex" }'
        response = requests.request("POST", self.URL, headers=HEADERS, data=payload)
        response_data = json.loads(response.text)
        select_index = response_data.get('SelectIndex', None)

        if media_state in ["playing", "on"]:  # Check for playing state
            title = self.get_state(self.MEDIA_PLAYER, attribute="media_title")
            album_name_check = self.get_state(self.MEDIA_PLAYER, attribute="media_album_name") or title
            self.send_pic = album_name_check != self.album_name

            if title != "TV" and title is not None:
                normalized_title = unidecode(title)
                artist = self.get_state(self.MEDIA_PLAYER, attribute="media_artist")
                artist = artist if artist else ""
                normalized_artist = unidecode(artist) if artist else ""
                picture = self.get_state(self.MEDIA_PLAYER, attribute="entity_picture")
                gif_base64, font_color, recommended_font_color, brightness, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative = self.process_picture(picture)
                new_attributes = {"artist": artist,"normalized_artist": normalized_artist, "media_title": title,"normalized_title": normalized_title, "media_picture_gif_base64": gif_base64, "font_color": font_color, "font_color_alternative": recommended_font_color, "background_color_brightness": brightness, "background_color": background_color, "color_alternative_rgb": most_common_color_alternative, "background_color_rgb": background_color_rgb, "recommended_font_color_rgb": recommended_font_color_rgb, "color_alternative": most_common_color_alternative_rgb,}
                self.set_state(self.SENSOR, state="on", attributes=new_attributes)
                payload = {"Command":"Draw/CommandList", "CommandList":[{"Command":"Channel/OnOffScreen", "OnOff":1},{"Command": "Draw/ResetHttpGifId"},{"Command": "Draw/SendHttpGif", "PicNum": 1, "PicWidth": 64, "PicOffset": 0, "PicID": 0, "PicSpeed": 1000, "PicData": gif_base64 }]}
                
                if self.send_pic:
                    self.album_name = album_name_check # Will not try to upload a new pic while listening to the same album
                    self.send_pixoo(payload)
                    if self.LIGHT:
                        self.control_light('on',background_color_rgb)
                
                if self.SHOW_TEXT and not self.FALLBACK:
                    color_font = font_color if self.FONT_C else recommended_font_color
                    payload = {"Command":"Draw/SendHttpText", "TextId": 3, "x": 0, "y": 48, "dir": 0, "font": self.FONT,"TextWidth": 64, "speed": 80, "TextString": normalized_artist + " - " + normalized_title + "                       ", "color": color_font, "align": 1}
                    self.send_pixoo(payload)
                
                if self.FALLBACK and self.FAIL_TXT:
                    payloads = self.create_payloads(normalized_artist, normalized_title, 13)
                    payload = {"Command":"Draw/CommandList", "CommandList": payloads}
                    self.send_pixoo(payload)

            else:
                payload = {"Command":"Draw/CommandList", "CommandList":[{"Command":"Channel/OnOffScreen", "OnOff":1},{"Command": "Draw/ResetHttpGifId"},{"Command": "Draw/SendHttpGif","PicNum": 1,"PicWidth": 64, "PicOffset": 0, "PicID": 0, "PicSpeed": 1000, "PicData": zlib.decompress(TV_ICON).decode() }]}
                self.send_pixoo(payload)
                if self.LIGHT:
                    self.control_light('off')
        else:
            self.album_name = "no music is playing and no album name"
                
            if self.FULL_CONTROL:
                payload = {"Command":"Draw/CommandList", "CommandList":[{"Command":"Draw/ClearHttpText"},{"Command": "Draw/ResetHttpGifId"},{"Command":"Channel/OnOffScreen", "OnOff":0} ]}
                time.sleep(4) # Delay to not turn off the screen when choosing music tracks while playing a track
            else:
                payload = {"Command":"Draw/CommandList", "CommandList":[{"Command":"Draw/ClearHttpText"},{"Command": "Draw/ResetHttpGifId"},{"Command":"Channel/SetIndex", "SelectIndex": 4 },{"Command":"Channel/SetIndex", "SelectIndex": select_index }]}
                
            media_state = self.get_state(self.MEDIA_PLAYER)
            if not media_state in ["playing", "on"]:
                self.send_pixoo(payload)
                self.set_state(self.SENSOR, state="off")
                if self.LIGHT:
                    self.control_light('off')

    def process_picture(self, picture):
        font_color = recommended_font_color = recommended_font_color_rgb = "#FFFFFF"
        background_color  = most_common_color_alternative_rgb = most_common_color_alternative = "#000000"
        background_color_rgb = tuple(random.randint(10, 200) for _ in range(3))
        brightness = 0
        
        try:
            img = self.get_image(picture)
            img = self.ensure_rgb(img)
            full_img = img        
            lower_part = img.crop(LOWER_PART_CROP)
            lower_part = self.ensure_rgb(lower_part)
            most_common_color = self.most_vibrant_color(lower_part)
            most_common_color_alternative_rgb = self.most_vibrant_color(full_img)
            most_common_color_alternative = '#%02x%02x%02x' % most_common_color_alternative_rgb
            brightness = int(sum(most_common_color) / 3)
            most_common_colors = [item[0] for item in Counter(lower_part.getdata()).most_common(10)]
            candidate_colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255), (255, 0, 255)]
            
            for color in candidate_colors:
                if color not in most_common_colors:
                    font_color = '#%02x%02x%02x' % color
                    break
            
            opposite_color = tuple(255 - i for i in most_common_color)
            recommended_font_color = '#%02x%02x%02x' % opposite_color
            enhancer = ImageEnhance.Contrast(full_img)
            full_img = enhancer.enhance(2.0)
            background_color_rgb = self.most_vibrant_color(full_img)
            background_color = '#%02x%02x%02x' % most_common_color_alternative_rgb
            recommended_font_color_rgb = opposite_color
            
            if self.TEXT_BG and self.SHOW_TEXT:
                lpc = (0,48,64,64)
                lower_part_img = img.crop(lpc)
                enhancer_lp = ImageEnhance.Brightness(lower_part_img)
                normalized = brightness / 255
                
                if normalized <= 0.5:
                    output_value = 0.2 + normalized * 0.6
                else:
                    output_value = 1.5 + (normalized - 0.5) * 0.6
                
                output_value = "{:.1f}".format(output_value)
                output_value = float(output_value)
                lower_part_img = enhancer_lp.enhance(output_value)
                img.paste(lower_part_img, lpc)
            
            pixels = self.get_pixels(img)
            b64 = base64.b64encode(bytearray(pixels))
            gif_base64 = b64.decode("utf-8")
            self.FALLBACK = False

        except Exception as e:
            self.log(f"Error processing image. Using defualt values: {e}")
            self.FALLBACK = True
            
            if self.FAIL_TXT:
                gif_base64 = zlib.decompress(BLK_SCR).decode()
            else:
                gif_base64 = zlib.decompress(NO_IMAGE).decode()
        
        return gif_base64, font_color, recommended_font_color, brightness, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative

    def get_image(self, picture):
        try:
            response = requests.get(f"{self.HA_URL}{picture}")
            img = Image.open(BytesIO(response.content))
            img = img.convert("RGB")
            
            if self.CROP_BORDERS:
                temp_img = img
                
                if self.CROP_EXTRA:
                    img = img.filter(ImageFilter.BoxBlur(5))
                    enhancer = ImageEnhance.Brightness(img)
                    img = enhancer.enhance(1.95)
                
                try:
                    np_image = np.array(img)
                    edge_pixels = np.concatenate([np_image[0, :], np_image[-1, :], np_image[:, 0], np_image[:, -1]])
                    colors, counts = np.unique(edge_pixels, axis=0, return_counts=True)
                    border_color = colors[counts.argmax()]
                    dists = np.linalg.norm(np_image - border_color, axis=2)
                    mask = dists < 100  #TOLERANCE
                    coords = np.argwhere(mask == False)
                    x_min, y_min = coords.min(axis=0)
                    x_max, y_max = coords.max(axis=0) + 1
                    width, height = x_max - x_min, y_max - y_min
                    max_size = max(width, height)
                    x_center, y_center = (x_min + x_max) // 2, (y_min + y_max) // 2
                    x_min = max(0, x_center - max_size // 2)
                    y_min = max(0, y_center - max_size // 2)
                    x_max = min(np_image.shape[0], x_min + max_size)
                    y_max = min(np_image.shape[1], y_min + max_size)
                    if x_max - x_min < max_size:
                        x_min = x_max - max_size
                    if y_max - y_min < max_size:
                        y_min = y_max - max_size  
                    
                    img = temp_img
                    img = img.crop((y_min, x_min, y_max, x_max))    
                
                except Exception as e:
                    self.log(f"Failed to crop: {e}")  
                    enhancer = ImageEnhance.Contrast(temp_img)
                    temp_img = enhancer.enhance(2.0)
                    img = temp_img
                
            if self.CONTRAST:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.5) # 50% contrast
            
            img.thumbnail((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.LANCZOS)
            #self.save_img(img)
            return img
        
        except UnidentifiedImageError:
            self.log("Unable to identify image file.")
            self.FALLBACK = True
            return None

    def send_pixoo(self, payload_command):
        response = requests.post(self.URL, headers=HEADERS, data=json.dumps(payload_command))
        if response.status_code != 200:
            self.log(f"Failed to send REST: {response.content}")
    
    def ensure_rgb(self, img):
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img

    def get_pixels(self, img):
        if img.mode == "RGB":
            pixels = [item for p in list(img.getdata()) for item in p]
        else:
            pixels = list(img.getdata())
        return pixels

    def split_string(self, text, length):
        words = text.split(' ')
        lines = []
        current_line = ''
        
        for word in words:
            if len(current_line) + len(word) > length: 
                lines.append(current_line)
                current_line = word
            else:
                current_line += ' ' + word if current_line else word  
        
        lines.append(current_line)
        return lines

    def create_payloads(self, normalized_artist, normalized_title, x):
        artist_lines = self.split_string(normalized_artist, x)
        title_lines = self.split_string(normalized_title, x)
        all_lines = artist_lines + title_lines
        
        if len(all_lines) > 4:
            all_lines[3] += ' ' + ' '.join(all_lines[4:])
            all_lines = all_lines[:4]
        
        start_y = (64 - len(all_lines) * 15) // 2
        payloads = [{"Command":"Draw/ClearHttpText"}] 
        
        for i, line in enumerate(all_lines):
            payload = {"Command":"Draw/SendHttpText", "TextId": i+1, "x": 0, "y": start_y + i*15, "dir": 0, "font": self.FONT, "TextWidth": 64,"speed": 80, "TextString": line, "color": "#a0e5ff" if i < len(artist_lines) else "#f9ffa0", "align": 2}
            payloads.append(payload)
        return payloads
    
    def control_light(self, action, background_color_rgb=None):
        service_data = {'entity_id': self.LIGHT}
        if action == 'on':
            service_data.update({'rgb_color': background_color_rgb, 'transition': 2 })
        try:
            self.call_service(f'light/turn_{action}', **service_data)
        except Exception as e:
            self.log(f"Light Error: {self.LIGHT} - {e}\n{traceback.format_exc()}")
            
    def most_vibrant_color(self, full_img):
        full_img.thumbnail((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.LANCZOS)
        color_counts = Counter(full_img.getdata())
        most_common_colors = color_counts.most_common()
        
        for color, count in most_common_colors:
            r, g, b = color
            max_color = max(r, g, b)
            min_color = min(r, g, b)
            if max_color + min_color > 400 or max_color - min_color < 50:  
                continue
            if max_color - min_color < 100:  
                continue
            return color
        
        return tuple(random.randint(100, 200) for _ in range(3))
