import redis
from datetime import datetime

server_1 = redis.Redis(host='mycrdb-db.r1.34.152.54.45.nip.io',
                    port=443,
                    password='mycrdb',
                    ssl=True,
                    ssl_cert_reqs='required',
                    ssl_ca_certs='cert_r1.pem')

server_2 = redis.Redis(host='mycrdb-db.r2.34.130.42.227.nip.io',
                    port=443,
                    password='mycrdb',
                    ssl=True,
                    ssl_cert_reqs=None,
                    ssl_ca_certs='cert_r2.pem')

for x in range(5):

    dateTimeObj = datetime.now()
    timestampStr = dateTimeObj.strftime("%d-%b-%Y (%H:%M:%S.%f)")

    server_1.set('mykey', 'Hello from Python! ' + timestampStr)

    value = server_1.get('mykey')
    print("Getting key from  region 1 : "+str(value))

    value2 = server_2.get('mykey')
    print("Getting key from  region 2 : "+str(value2))
