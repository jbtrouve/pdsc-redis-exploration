# Produce activity

import time
import redis
from datetime import datetime

server_1 = redis.Redis(host='mycrdb-db.r1.34.152.39.94.nip.io',
                    port=443,
                    password='mycrdb',
                    ssl=True,
                    ssl_cert_reqs='required',
                    ssl_ca_certs='cert_r1.pem')

server_2 = redis.Redis(host='mycrdb-db.r2.34.124.112.169.nip.io',
                    port=443,
                    password='mycrdb',
                    ssl=True,
                    ssl_cert_reqs='required',
                    ssl_ca_certs='cert_r2.pem')

for xx in range(500):

    # Write to region 1, read from region 2

    dateTimeObj = datetime.now()
    # timestampStr = dateTimeObj.strftime("%d-%b-%Y (%H:%M:%S.%f)")
    timestampStr = dateTimeObj.strftime("%H:%M:%S.%f")
    my_second = dateTimeObj.strftime("%S")

    value = timestampStr
    key1 = "Site-1-" + my_second
    key2 = "Site-2-" + my_second

    try:
      server_1.set(key1, value)
      set_status_1 = "set_1:OK   "
    except:
      set_status_1 = "set_1:ERROR"

    time.sleep(1.0)

    try:
      value_from_2 = server_2.get(key1)
      if not value_from_2:
        value_from_2 = ""
      get_status_2 = "get_2:OK   "
    except:
      value_from_2 = "???"
      get_status_2 = "get_2:ERROR"

    if value_from_2 == value:
      value_diag_2 = "OK"
    else:
      value_diag_2 = "**different**"

    print( '{:5} 1->2 {} {} {}   {} {} ?= {} {}'.format(xx, timestampStr, key1, set_status_1, get_status_2, value_from_2, value, value_diag_2) )

    ###############################################################################################
    # Write to region 2, read from region 1

    dateTimeObj = datetime.now()
    timestampStr = dateTimeObj.strftime("%H:%M:%S.%f")
    my_second = dateTimeObj.strftime("%S")

    value = timestampStr
    key1 = "Site-1-" + my_second
    key2 = "Site-2-" + my_second

    try:
      server_2.set(key1, value)
      set_status_2 = "set_2:OK   "
    except:
      set_status_2 = "set_2:ERROR"

    time.sleep(0.5)

    try:
      value_from_1 = server_1.get(key1)
      if not value_from_1:
        value_from_1 = ""
      get_status_1 = "get_2:OK   "
    except:
      value_from_1 = "???"
      get_status_1 = "get_2:ERROR"

    if value_from_1 == value:
      value_diag_1 = "OK"
    else:
      value_diag_1 = "**different**"

    print( '{:5} 2->1 {} {} {}   {} {} ?= {} {}\n'.format(xx, timestampStr, key2, set_status_2, get_status_1, value_from_1, value, value_diag_1) )
