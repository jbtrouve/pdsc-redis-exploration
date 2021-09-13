# Exploring Redis Enterprise active-active clusters
This collection was used to set up active-active Redis Enterprise clusters in distinct regions using a personal Google account.

Reference (given by Redis Solutions architect): https://github.com/quintonparker/redis-enterprise-k8s-docs/blob/aws-eks-active-active/eks-active-active.md

## Setup 

    cd ~/active-active-redis

### Download sample code
    git clone https://github.com/quintonparker/redis-enterprise-k8s-docs.git -b aws-eks-active-active aws-eks-active-active

### Download Redis Operator
    VERSION=$(curl --silent https://api.github.com/repos/RedisLabs/redis-enterprise-k8s-docs/releases/latest | grep tag_name | awk -F'"' '{print $4}')
    echo $VERSION
               v6.0.20-12
    curl --silent -O https://raw.githubusercontent.com/RedisLabs/redis-enterprise-k8s-docs/$VERSION/bundle.yaml
## Build region 1

    gcloud config set project unified-skein-322012       # your project will be different

### Create cluster
    ./0-gke-cluster 1

### Deploy Redis Operator
    ./1-operator 1		# ETA 20 seconds

### Create Redis Cluster
    ./2-rec 1

### Deploy REDB admission controller
    ./3-admission-controller 1

### Deploy webhook
    ./4-webhook 1

### Create test database (smoke test)
    ./5-smoketest-db 1

### Configure Ingress
    ./6-ingress 1

### Configure public IP for cluster-to-cluster replication
    ./7-patch-rec 1

### Configure public IP for web UI
    ./8-ui-lb 1

## Build region 2

    ./0-gke-cluster 2
    ./1-operator 2
    ./2-rec 2
    ./3-admission-controller 2
    ./4-webhook 2
    ./5-smoketest-db 2
    ./6-ingress 2
    ./7-patch-rec 2
    ./8-ui-lb 2
## Build region 3

    ./0-gke-cluster 3
    ./1-operator 3
    ./2-rec 3
    ./3-admission-controller 3
    ./4-webhook 3
    ./5-smoketest-db 3
    ./6-ingress 3
    ./7-patch-rec 3
    ./8-ui-lb 3
## Show commands to configure active-active REDB (regions 1, 2 and 3)

    ./9-act-act-db

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

## Prepare for external access
### Get UI coordinates for each cluster
    ./show-ui-access-info
### From UI, change DB parameters for client SSL communication. 

**For each Redis cluster** , from UI:
- top menu: databases
- click on database _mycrdb_
- click tab _configuration_
- click _Edit_ button at bottom of page
- Section TLS: select _Require TLS for All Communications_
- Section TLS: UNcheck _Enforce client authentication_
- click _Update_ button at bottom of page

### From UI, obtain client certificate. 
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

## Use a container to run FMEA tests 
Get names of the active-active databases (see "Host for DB client")

    ./aa-get-client-info

On the GKE cluster where Redis DB is hosted, deploy a container with image redislabs/redis

    kubectl apply -f redis-client.yaml -n redis

Connect to new container

    ./connect-to-client

Copy _produce-activity.py_ to /tmp (on the client container)

    curl https://raw.githubusercontent.com/jbtrouve/pdsc-redis-exploration/main/produce-activity.py >produce-activity.py

Adjust name of databases

    vi produce-activity.pl
       # Change all mycrdb-db.r2.NN.NN.NN.NN.nip.io  to the proper _Host for DB client_

Copy CA certificate files to /tmp

Run sample program (use -u if piping to _tee_ ):

    python -u produce-activity.py | tee activity.out

In another session on the same pod, run memtier_benchmark; use output of *aa-get-client-info* to get the proper IPs.  In our case 2 runs at 5000 reps (* 4 threadstakes about 1 minute.

    memtier_benchmark -s mycrdb-db.r1.34.152.39.94.nip.io -p 443 -a mycrdb --tls --sni mycrdb-db.r1.34.152.39.94.nip.io --cacert cert_r1.pem -R -n 5000 -d 25 -R 16 --key-pattern=P:P --ratio=1:100 --hide-histogram --run-count=2

The End.
