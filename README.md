# Exploring Redis Enterprise active-active clusters
This collection was used to set up active-active Redis Enterprise clusters in distinct regions using a personal Google account.

Reference (given by Redis Solutions architect): https://github.com/quintonparker/redis-enterprise-k8s-docs/blob/aws-eks-active-active/eks-active-active.md

## Setup 

    cd ~/active-active-redis

### Download sample code
    git clone https://github.com/quintonparker/redis-enterprise-k8s-docs.git -b aws-eks-active-active aws-eks-active-active

### Download Redis Operator
    VERSION=$(curl --silent https://api.github.com/repos/RedisLabs/redis- enterprise-k8s-docs/releases/latest | grep tag_name | awk -F'"' '{print $4}')
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

## Test DB access

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

The End.
