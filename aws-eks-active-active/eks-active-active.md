# Creating an Active Active demo deployment using AWS EKS

Although this doc is AWS and EKS specific, the instructions below can be applied to multi/hybrid cloud topologies with minimal adaptation because in principle each EKS cluster is decoupled from the knowledge that it is collaborating with a fellow EKS cluster

_Please note all instructions contained herein is demo quality! Do not use verbatim for production environments!_

In this quickie step-by-step manual we'll be 

1. Creating an EKS cluster in US-EAST-1
2. Deploying Redis Enterprise Operator to US-EAST-1
3. Deploying and Configuring Ingress Nginx to facilitate operating Active-Active database(s)
4. Creating another EKS cluster in US-WEST-1
5. Deploying Redis Enterprise Operator to US-WEST-1
6. Deploying and Configuring Ingress Nginx to facilitate operating Active-Active database(s)
6. Creating an Active-Active database with US-EAST-1 and US-WEST-1 as participating CRDB instances
7. Running a simple test for Active-Active replication

## Prequisites

1. AWS security credentials
2. IAM permissions to deploy EKS clusters + iam:AttachRolePolicy + iam:DetachRolePolicy 
3. *nix terminal
4. git
6. kubectl
7. eksctl
8. curl (not a hard requirement)
9. jq (not a hard requirement)

## Create a local workspace

Hope over to your terminal and clone this repo somewhere

```
git clone git@github.com:quintonparker/redis-enterprise-k8s-docs.git 
```

```
git co eks-active-active
```
Note: this is a branch off the latest known release tag at time of writing https://github.com/RedisLabs/redis-enterprise-k8s-docs/releases/tag/v6.0.20-4

## Creating an EKS cluster in US-EAST-1

### Please note
1. This will create a self-managed EKS cluster. You may want a managed one or want to use Fargate instead. Should work too but I have not tested that (yet)
2. t3.xlarge is selected because its cost-effective and this is just a simple demo. Best to size the use-case and choose more appropriate compute family/instance for real-world use-cases
3. Ideally we want 3 worker nodes in accordance with Redis Enterprise Cluster architecture. See https://redislabs.com/redis-enterprise/technology/redis-enterprise-cluster-architecture/

```
eksctl create cluster --name east --nodegroup-name standard-workers --node-type t3.xlarge --nodes 3 --nodes-min 1 --nodes-max 4 --node
-ami auto --tags "Owner=quinton@redislabs.com" --region us-east-1
```

This will take 10-20mins. Once completed run `kubectl config get-contexts`. Response should resemble:

```
kubectl config get-contexts                                            
CURRENT   NAME                                        CLUSTER                    AUTHINFO                                    NAMESPACE
*         iam-root-account@east.us-east-1.eksctl.io   east.us-east-1.eksctl.io   iam-root-account@east.us-east-1.eksctl.io
```

## Deploying Redis Enterprise Operator

The following instructions is a distillation of https://github.com/quintonparker/redis-enterprise-k8s-docs#installation for demo purposes only

For production deployments please refer to https://github.com/quintonparker/redis-enterprise-k8s-docs#installation as it contains pertinent information!

### Create a new namespace

```bash
kubectl create namespace east
```
```
kubectl config set-context --current --namespace=east
```

```
kubectl config get-contexts
```

Response should resemble:
```
CURRENT   NAME                                        CLUSTER                    AUTHINFO                                    NAMESPACE
*         iam-root-account@east.us-east-1.eksctl.io   east.us-east-1.eksctl.io   iam-root-account@east.us-east-1.eksctl.io   east
```

### Deploy the operator bundle

To deploy the default installation with `kubectl`, the following command will deploy a bundle of all the yaml declarations required for the operator:

```bash
kubectl apply -f bundle.yaml
```

Run `kubectl get deployment --watch` and verify redis-enterprise-operator deployment is running.

Response should resemble:

```bash
NAME                               READY   UP-TO-DATE   AVAILABLE   AGE
redis-enterprise-operator          1/1     1            1           2m
```

### Redis Enterprise Cluster custom resource - `RedisEnterpriseCluster`

Create a `RedisEnterpriseCluster`(REC) using the default configuration, which is suitable for development type deployments and works in typical scenarios. The full list of attributes supported through the Redis Enterprise Cluster (REC) API can be found [HERE](redis_enterprise_cluster_api.md). Some examples can be found in the examples folder. 

```bash
kubectl apply -f examples/v1/rec.yaml
```

4. Run `kubectl get rec --watch` and verify creation was successful. `rec` is a shortcut for RedisEnterpriseCluster. The cluster takes around 5-10 minutes to come up.

Response should resemble:
```
NAME   NODES   VERSION     STATE     SPEC STATUS   LICENSE STATE   SHARDS LIMIT   LICENSE EXPIRATION DATE   AGE
rec    3       6.0.20-69   Running   Valid         Valid           4              2021-06-11T15:25:56Z      20h
```

### Redis Enterprise Database (REDB) Admission Controller

The Admission Controlller is recommended for use. It uses the Redis Enterprise Cluster to dynamically validate that REDB resources as configured by the operator are valid.

#### Steps to configure the Admission Controller:

1. Install the Admission Controller via a bundle:
```shell script
kubectl create -f admission.bundle.yaml
```
Wait for the secret to be created:
```shell script
    kubectl get secret admission-tls
    NAME            TYPE     DATA   AGE
    admission-tls   Opaque   2      2m43s
```
2. Enable the Kubernetes webhook using the generated certificate

    **NOTE**: One must replace REPLACE_WITH_NAMESPACE in the following command with the namespace the REC was installed into.

    ```shell script
    # save cert
    CERT=`kubectl get secret admission-tls -o jsonpath='{.data.cert}'`
    sed 's/NAMESPACE_OF_SERVICE_ACCOUNT/REPLACE_WITH_NAMESPACE/g' admission/webhook.yaml | kubectl create -f -

    # create patch file
    cat > modified-webhook.yaml <<EOF
    webhooks:
    - admissionReviewVersions:
    clientConfig:
        caBundle: $CERT
    name: redb.admission.redislabs
    admissionReviewVersions: ["v1beta1"]
    EOF
    # patch webhook with caBundle
    kubectl patch ValidatingWebhookConfiguration redb-admission --patch "$(cat modified-webhook.yaml)"
    ```
3. Verify the installation

In order to verify that the all the components of the Admission Controller are installed correctly, we will try to apply an invalid resource that should force the admission controller to reject it.  If it applies succesfully, it means the admission controller has not been hooked up correctly.

```shell script
$ kubectl apply -f - << EOF
apiVersion: app.redislabs.com/v1alpha1
kind: RedisEnterpriseDatabase
metadata:
    name: redis-enterprise-database
spec:
    evictionPolicy: illegal
EOF
```
    
This must fail with an error output by the admission webhook redb.admisison.redislabs that is being denied because it can't get the login credentials for the Redis Enterprise Cluster as none were specified.

```shell script
Error from server: error when creating "STDIN": admission webhook "redb.admission.redislabs" denied the request: eviction_policy: u'illegal' is not one of [u'volatile-lru', u'volatile-ttl', u'volatile-random', u'allkeys-lru', u'allkeys-random', u'noeviction', u'volatile-lfu', u'allkeys-lfu']
```
> Note: procedure to enable admission is documented with further detail [here](admission/README.md

#### Redis Enterprise Database custom resource - `RedisEnterpriseDatabase`

This step is optional. As a sanity check that you have a healthy `rec` it is a good idea to create a regular database as a smoke test that everything so far is a-ok.

```yaml
cat << EOF > /tmp/redis-enterprise-database.yml
apiVersion: app.redislabs.com/v1alpha1
kind: RedisEnterpriseDatabase
metadata:
    name: redis-enterprise-database
spec:
    memorySize: 100MB
EOF
kubectl apply -f /tmp/redis-enterprise-database.yml
```

```
kubectl exec -it rec-0 -- rladmin status
```

Response should resemble:
```
Defaulted container "redis-enterprise-node" out of: redis-enterprise-node, bootstrapper

CLUSTER NODES:
NODE:ID ROLE   ADDRESS       EXTERNAL_ADDRESS HOSTNAME SHARDS CORES FREE_RAM   PROVISIONAL_RAM VERSION   STATUS
*node:1 master 192.168.3.165                  rec-0    1/100  4     1.97GB/4GB 1.16GB/3.28GB   6.0.20-69 OK    
node:2  slave  192.168.52.30                  rec-1    0/100  4     2.51GB/4GB 1.74GB/3.28GB   6.0.20-69 OK    
node:3  slave  192.168.40.50                  rec-2    0/100  4     2.52GB/4GB 1.75GB/3.28GB   6.0.20-69 OK    

DATABASES:
DB:ID NAME                      TYPE  STATUS SHARDS PLACEMENT REPLICATION PERSISTENCE ENDPOINT                                    
db:3  redis-enterprise-database redis active 1      dense     disabled    disabled    redis-10652.rec.east.svc.cluster.local:10652

ENDPOINTS:
DB:ID     NAME                           ID             NODE    ROLE    SSL     
db:3      redis-enterprise-database      endpoint:3:1   node:1  single  No      

SHARDS:
DB:ID NAME                      ID      NODE   ROLE   SLOTS   USED_MEMORY STATUS
db:3  redis-enterprise-database redis:1 node:1 master 0-16383 2.12MB      OK    
```

A simple check that the database endpoint is ready for action

1. Retrieve the database password `kubectl get secret redb-redis-enterprise-database -o jsonpath="{.data.password}" | base64 --decode` and replace `XXXXXX` next command
2. `PING` the endpoint `kubectl exec -it rec-0 -- redis-cli -h redis-10652.rec.east.svc.cluster.local -p 10652 -a XXXXXX PING`

Output should be `PONG`!

If you want to access the GUI...

1. Create a port-forward `kubectl port-forward rec-0 8443:8443`
2. Retrieve the username `kubectl get secret rec -o jsonpath="{.data.username}" | base64 --decode` (should be `demo@redislabs.com`)
2. Retrieve the password `kubectl get secret rec -o jsonpath="{.data.password}" | base64 --decode`
3. Hop to a web browser `https://localhost:8443` (accept self-signed certificate)

### Deploying & configuring NGINX Ingress Controller

Refer to opening paragraph. Let's facilitate inter-cluster comms in a way that can translate easily to multi-cloud or hybrid-cloud topologies.

To enable Active-Active we need to enable the necessary inter-cluster communication. Therefore, we need to pay attention to the Active-Active ports documented here https://docs.redislabs.com/latest/rs/administering/designing-production/networking/port-configurations/

No, we won't willy nilly open up port ranges but using NGINX Ingress Controller we can achieve this quite elegantly https://kubernetes.github.io/ingress-nginx/deploy/#network-load-balancer-nlb

Note: the bundled `ingress-nginx-deploy.yaml` file is a fork of https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v0.46.0/deploy/static/provider/aws/deploy.yaml with customized args to enable Ingress Nginx to operate as a layer 4 Ingress supporting ssl passthru. See https://github.com/quintonparker/redis-enterprise-k8s-docs/commit/a8c10382392230aa075336fb98ac9971d5d7e6ac#diff-f95f67657ef1b132b47b8c327881ae71aba4b6ef9a6d51d259f3986eed48db9d

1. `kubectl apply -f ingress-nginx-deploy.yaml`. 
2. `kubectl get all -n ingress-nginx --watch`
Output should resemble:

```
NAME                                            READY   STATUS      RESTARTS   AGE
pod/ingress-nginx-admission-create-5fg66        0/1     Completed   0          21h
pod/ingress-nginx-admission-patch-5r6cr         0/1     Completed   0          21h
pod/ingress-nginx-controller-7d5999f4d9-wkds2   1/1     Running     0          21h

NAME                                         TYPE           CLUSTER-IP       EXTERNAL-IP                                                                     PORT(S)                      AGE
service/ingress-nginx-controller             LoadBalancer   10.100.168.240   a27d2f1f9c36c43f5a9f428a60296554-7577f64680ea608f.elb.us-east-1.amazonaws.com   80:31065/TCP,443:32217/TCP   21h
service/ingress-nginx-controller-admission   ClusterIP      10.100.110.173   <none>                                                                          443/TCP                      21h

NAME                                       READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/ingress-nginx-controller   1/1     1            1           21h

NAME                                                  DESIRED   CURRENT   READY   AGE
replicaset.apps/ingress-nginx-controller-7d5999f4d9   1         1         1       21h

NAME                                       COMPLETIONS   DURATION   AGE
job.batch/ingress-nginx-admission-create   1/1           4s         21h
job.batch/ingress-nginx-admission-patch    1/1           2s         21h
```

The value in the `EXTERNAL-IP` column will be unique to your deployment and it represents the public DNS name (automatically assigned by AWS) that resolves to a public static IP belonging to an AWS Network Load Balancer.

Next is to configure Ingress Nginx to route traffic to using Redis Enterprise Operator support for k8s annotations

For this section we are going to use `nip.io` as a quick/easy/dirty hack but remember this is never recommended for production. If you access to a TLD then feel free to use that instead and configure CNAMEs etc. via Route53 or whatever DNS provider you are using.

1. `ping` the LoadBalancer EXTERNAL-IP to learn the public static ip eg. `ping a27d2f1f9c36c43f5a9f428a60296554-7577f64680ea608f.elb.us-east-1.amazonaws.com`
2. then edit `rec-east.yaml` accordingly replacing `100.26.91.141` with your detected IP for `apiIngressUrl` and `dbIngressSuffix` properties
3. run `kubectl apply -f rec-east.yaml`

As a smoke test that ingress is configured correctly the following is a REST API call that outputs the configured databases for this cluster

```
curl -L -v -k GET https://api.east.100.26.91.141.nip.io/v1/bdbs -u "demo@redislabs.com:XXXXXX" -H "Content-Type: application/json" | jq '.[]'
```

## Creating an EKS cluster and installing Redis Enterprise Operator in US-WEST-1

Repeat same steps as above for US-EAST-1 except of course
* substitute all occurrences of `east` for `west`
* remember, the Ingress LoadBalancer EXTERNAL-IP will resolve to a different IP
* the `west` cluster will come with different k8s secrets/passwords for the Databases, UI and REST API etc.

### Switching kubectl contexts

eksctl will automatically add a new context to your `~/.kube/config`. To display all your available contexts

```
kubectl config get-contexts                                          
CURRENT   NAME                                        CLUSTER                    AUTHINFO                                    NAMESPACE
*         iam-root-account@east.us-east-1.eksctl.io   east.us-east-1.eksctl.io   iam-root-account@east.us-east-1.eksctl.io   east
          iam-root-account@west.us-west-1.eksctl.io   west.us-west-1.eksctl.io   iam-root-account@west.us-west-1.eksctl.io   west
```

To switch context
```
kubectl config use-context iam-root-account@west.us-west-1.eksctl.io 
```

And vice versa

### Retrieving rec username and password
```
kubectl get secret rec -o jsonpath="{.data.username}" | base64 --decode
```

```
kubectl get secret rec -o jsonpath="{.data.password}" | base64 --decode
```

## The final step. Creating an Active-Active database

### Constructing crdb-cli command

Assuming `east` and `west` custers are deployed and configured successfully as above, we now need to run the `crdb-cli` command to create our active-active database

Because this command is fairly complex there are a set of parameters we need to gather per region viz.

* `fqdn` ~ the cluster fqdn. displayed on `cluster` page of the UI eg. `rec.west.svc.cluster.local` or query the API to find it `curl  -s -k GET https://api.east.100.26.91.141.nip.io/v1/cluster -u "{username}:{password}" -H "Content-Type: application/json" | jq '.name'`
* `url` ~ the same as `apiIngressUrl` ie. What you configured in `rec-(east|west).yaml`
* `username` ~ `rec` username. See above
* `password` ~ `rec` password. See above
* `replication_endpoint` ~ in the format `{database_name}.{dbIngressSuffix}:443`. `dbIngressSuffix` is what you configured in `rec-(east|west).yaml`
* `replication_tls_sni` ~ in the format `{database_name}.{dbIngressSuffix}`. `dbIngressSuffix` is what you configured in `rec-(east|west).yaml`

### Running crdb-cli command

Please note regarding the example fully constructed `crdb-cli` command:
1. This can be executed from a `rec-0` pod in either cluster
2. This is a very naive database configuration as it is only 100m memory limit etc.
3. The `{database_name}` chosen is simply `mycrdb`

```
kubectl exec -it rec-0 -- /bin/bash
```

```
crdb-cli crdb create --name mycrdb --memory-size 100m --encryption yes \
 --instance fqdn=rec.west.svc.cluster.local,url=https://api.west.54.193.88.213.nip.io,username=demo@redislabs.com,password=XXXXXX,replication_endpoint=mycrdb-db.west.54.193.88.213.nip.io:443,replication_tls_sni=mycrdb-db.west.54.193.88.213.nip.io\
 --instance fqdn=rec.east.svc.cluster.local,url=https://api.east.100.26.91.141.nip.io,username=demo@redislabs.com,password=XXXXXX,replication_endpoint=mycrdb-db.east.100.26.91.141.nip.io:443,replication_tls_sni=mycrdb-db.east.100.26.91.141.nip.io
 ```
 Output should be something like

 ```
 Task 3283a9dd-d3ae-417d-be3f-32e069904197 created
  ---> Status changed: queued -> started
  ---> CRDB GUID Assigned: crdb:58e9e495-93d7-47b1-8507-dcd61a877918
  ---> Status changed: started -> finished
```

### Smoke test

Against either region run `kubectl exec -it rec-0 -- rladmin status`. Output should resemble:

```
Defaulted container "redis-enterprise-node" out of: redis-enterprise-node, bootstrapper
CLUSTER NODES:
NODE:ID ROLE   ADDRESS       EXTERNAL_ADDRESS HOSTNAME SHARDS CORES FREE_RAM   PROVISIONAL_RAM VERSION   STATUS
*node:1 master 192.168.3.165                  rec-0    1/100  4     1.98GB/4GB 1.16GB/3.28GB   6.0.20-69 OK    
node:2  slave  192.168.52.30                  rec-1    1/100  4     2.51GB/4GB 1.74GB/3.28GB   6.0.20-69 OK    
node:3  slave  192.168.40.50                  rec-2    1/100  4     2.52GB/4GB 1.75GB/3.28GB   6.0.20-69 OK    

DATABASES:
DB:ID NAME                      TYPE  STATUS SHARDS PLACEMENT REPLICATION PERSISTENCE ENDPOINT                                    
db:3  redis-enterprise-database redis active 1      dense     disabled    disabled    redis-10652.rec.east.svc.cluster.local:10652
db:4  mycrdb                    redis active 1      dense     enabled     disabled    redis-16534.rec.east.svc.cluster.local:16534

ENDPOINTS:
DB:ID     NAME                           ID             NODE    ROLE    SSL     
db:3      redis-enterprise-database      endpoint:3:1   node:1  single  No      
db:4      mycrdb                         endpoint:4:1   node:2  single  Replica 

SHARDS:
DB:ID NAME                      ID      NODE   ROLE   SLOTS   USED_MEMORY STATUS
db:3  redis-enterprise-database redis:1 node:1 master 0-16383 2.08MB      OK    
db:4  mycrdb                    redis:2 node:2 master 0-16383 4.88MB      OK    
db:4  mycrdb                    redis:3 node:3 slave  0-16383 5.41MB      OK 
```

Using the `crdb` endpoint value lets set a key in this region eg.
```
kubectl exec -it rec-0 -- redis-cli -h redis-16534.rec.west.svc.cluster.local -p 16534 set hello world
```

Now switch to other region context and retrieve the replicated key. Note the endpoint name will differ!
```
kubectl config use-context iam-root-account@east.us-east-1.eksctl.io
```

```
kubectl exec -it rec-0 -- redis-cli -h redis-16534.rec.east.svc.cluster.local -p 16534 get hello
```

The End. Happy Geo Replicating