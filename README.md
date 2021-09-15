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
## Build region 3 (only if using 3 regions)

    ./0-gke-cluster 3
    ./1-operator 3
    ./2-rec 3
    ./3-admission-controller 3
    ./4-webhook 3
    ./5-smoketest-db 3
    ./6-ingress 3
    ./7-patch-rec 3
    ./8-ui-lb 3
## Configure active-active DB (all regions)

    ./9-act-act-db          # creates custom command based on actual IPs and saves to script
    ./go-build-aa-database  # actually creates DB

## Deploy container for DB client (from where tests are run)

    ./10-deploy-redis-client

## Adjust Redis cluster's SSL parameters for proper DB client access
### Get UI coordinates for each cluster
    ./show-ui-access-info       #  take note of this (notepad file, etc)
### From UI, change DB parameters for client SSL communication. 
**For each Redis cluster** , from UI:
- top menu: databases
- click on database _mycrdb_
- click tab _configuration_
- click _Edit_ button at bottom of page
- Section TLS: select _Require TLS for All Communications_
- Section TLS: UNcheck _Enforce client authentication_
- click _Update_ button at bottom of page

## Deploy test tools to client container
### Get proxy (CA) certificates needed for client access
    ./show-proxy-certs       #  take note of this (notepad file, etc)
### Get names of the active-active databases (see "Host for DB client")
    ./aa-get-client-info      #  take note of this, too

### Access client container
    ./connect-to-client
    cd /tmp

### Deploy the test program (needs python)
    curl https://raw.githubusercontent.com/jbtrouve/pdsc-redis-exploration/main/produce-activity.py >produce-activity.py

### Adjust name of databases in python program
    vi produce-activity.pl
       # Change all mycrdb-db.r2.NN.NN.NN.NN.nip.io  to the proper _Host for DB client_

### Deploy proxy certificates
    cat >cert_r1.pem
         ### paste certificate for region 1 cluster
    ^D
    cat >cert_r2.pem
         ### paste certificate for region 2 cluster
    ^D

### Run sample program 
    python produce-activity.py      # stop with Ctrl-C
Note: use -u if piping output to _tee_ 

### Test memtier_benchmark
Use output of *aa-get-client-info* to get the proper IPs.  Here, 2 runs at 5000 reps (* 4 threads) take about 1 minute to complete.

    memtier_benchmark -s mycrdb-db.r1.34.152.39.94.nip.io -p 443 -a mycrdb --tls --sni mycrdb-db.r1.34.152.39.94.nip.io --cacert cert_r1.pem -R -n 5000 -d 25 -R 16 --key-pattern=P:P --ratio=1:100 --hide-histogram --run-count=2

**If everything is OK at this point then your test platform is valid.**

## Extra customization

## Extend UI timeout (to 10 hours)
    ./set-site-parameters 1
    ./connect-to-server 0
      rladmin cluster config cm_session_timeout_minutes 600
      exit

    ./set-site-parameters 2
    ./connect-to-server 0
      rladmin cluster config cm_session_timeout_minutes 600
      exit

