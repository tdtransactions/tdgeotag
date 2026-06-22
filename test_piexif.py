import piexif
from fractions import Fraction
from PIL import Image

def to_deg(value, loc):
    if value < 0:
        loc_value = loc[0]
    elif value > 0:
        loc_value = loc[1]
    else:
        loc_value = ""
    abs_value = abs(value)
    deg = int(abs_value)
    t1 = (abs_value-deg)*60
    min = int(t1)
    sec = round((t1 - min)* 60, 5)
    return (deg, min, sec, loc_value)

def change_to_rational(number):
    f = Fraction(str(number)).limit_denominator()
    return (f.numerator, f.denominator)

# Create a dummy image
img = Image.new('RGB', (10, 10))
img.save('test.jpg')

exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}}
lat = 10.0
lng = 20.0
lat_deg = to_deg(lat, ["S", "N"])
lng_deg = to_deg(lng, ["W", "E"])

# Original code
exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = lat_deg[3]
exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = [change_to_rational(lat_deg[0]), change_to_rational(lat_deg[1]), change_to_rational(lat_deg[2])]
exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = lng_deg[3]
exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = [change_to_rational(lng_deg[0]), change_to_rational(lng_deg[1]), change_to_rational(lng_deg[2])]

try:
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, 'test.jpg')
    print("Success with string")
except Exception as e:
    print("Error with string:", e)

# With bytes
exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = lat_deg[3].encode('ascii')
exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = lng_deg[3].encode('ascii')
try:
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, 'test.jpg')
    print("Success with bytes")
except Exception as e:
    print("Error with bytes:", e)

import os
os.remove('test.jpg')
