# Notes taken during exploration
Alternate tests from what's described in README.

## Test DB access (from server containers themselves)
    . ./set-site-parameters 1
    kubectl exec -it rec-$SITE-0 -- /bin/bash

    rladmin status # Identify DB ID of mycrdb (e.g. 4)
    bdb-cli 4  # replace 4 with actual DB ID
    set foo bar
    get foo

### In another window:
    . ./set-site-parameters 2   # Region 2
    kubectl exec -it rec-$SITE-0 -- /bin/bash
    . . .  same as above


## From UI, obtain client certificate. 
**For each Redis cluster** , from UI:
- top menu: settings
- click tab _general_
- section _Proxy Certificate_ : copy contents including BEGIN and END lines

## Use sample python program to test data access
- run *./aa-get-client-info* to get hostanames to use
- find Linux VM with python and redis module
- copy CA certificates in files called cert_r1.pem , cert_r2.pem , etc
- copy *sample_db_access.py* program there
- adjust program hostnames obtained above (and cert file names, if needed)
- run program:  python2 sample_db_access.py

## Use a container for redis-cli and friends 
On the GKE cluster where Redis DB is hosted:
- deploy a container with image redislabs/redis, name it redis-client
- identify pods named redis-client
- connect to one pod with:  kubectl exec -it redis-client-xyz-abc -- bash
- copy *sample_db_access.py* there (vi or cat)
- copy CA certificate files there, too
- run sample program:
    python sample_db_access.py
### Run redis-cli (sample, use your own IPs)
    redis-cli -h mycrdb-db.r1.34.152.54.45.nip.io -p 443 -a mycrdb --tls --sni mycrdb-db.r1.34.152.54.45.nip.io --cacert cert_r1.pem
### Run memtier_benchmark (sample for a quick test)
    memtier_benchmark -s mycrdb-db.r1.34.152.54.45.nip.io -p 443 -a mycrdb --tls --sni mycrdb-db.r1.34.152.54.45.nip.io --cacert cert_r1.pem -R -n 2000 -d 250 -R 16 --key-pattern=P:P --ratio=1:10
    memtier_benchmark --help   # to explain parameters
