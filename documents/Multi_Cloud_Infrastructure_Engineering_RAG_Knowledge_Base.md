# Multi-Cloud Infrastructure Engineering RAG Knowledge Base

**Document version:** 1.0  
**Review date:** 2026-11-17  
**Purpose:** Enterprise-grade grounding corpus for a local RAG assistant covering Azure, AWS, GCP, Windows Server, Linux, architecture, migration, operations, security, automation, backup/DR, FinOps, and ITSM.

**Scope note:** Cloud services, CLI syntax, limits, regions, and pricing change frequently. Always validate provider-specific commands, quotas, SKUs, and pricing against current official documentation before production use. Commands containing `<placeholder>` values require replacement.

## 1. Core operating principles

### 1.1 Production-first principles

- **Least privilege:** Grant only the permissions required for a role or workload.
- **Change control:** Treat production changes as controlled changes with approval, rollback, and validation.
- **Infrastructure as code:** Prefer declarative, version-controlled infrastructure definitions over manual console changes.
- **Observability:** Design monitoring, logging, alerting, and tracing before production rollout.
- **Recoverability:** Every critical workload must have documented RPO, RTO, backup, and recovery procedures.
- **Security by default:** Encrypt data in transit and at rest, restrict management access, use managed identities where possible, and log privileged activity.
- **Cost accountability:** Apply tagging, budgets, rightsizing, and ownership from day one.
- **Documentation:** Every architecture, change, incident, and handover should leave an auditable record.

### 1.2 Shared responsibility model

| Layer | Cloud provider responsibility | Customer responsibility |
|---|---|---|
| Physical data center | Facilities, hardware, physical security | Verify compliance requirements and contractual obligations |
| Hypervisor / cloud control plane | Platform availability and isolation | Configure services correctly |
| Operating system | Not managed for IaaS VMs | Patching, hardening, agents, configuration |
| Identity and access | Identity platform availability | RBAC design, MFA, privileged access, lifecycle |
| Network controls | Underlying network availability | VNet/VPC/firewall design, routing, segmentation |
| Application and data | Platform availability where applicable | Application code, data classification, backup, DR |
| Governance | Policy engines and tools | Policy definition, exceptions, enforcement, auditing |

### 1.3 Standard terminology

| Term | Meaning |
|---|---|
| Landing zone | Predefined, governed foundation for cloud workloads: identity, networking, security, logging, policy, and cost controls |
| Hub-and-spoke | Central shared-services network connected to isolated workload networks |
| RPO | Recovery Point Objective: maximum acceptable data loss |
| RTO | Recovery Time Objective: maximum acceptable recovery time |
| IaC | Infrastructure as Code |
| CMDB | Configuration Management Database |
| FinOps | Financial operations discipline for cloud cost management |
| Zero Trust | Security model based on explicit verification, least privilege, and continuous validation |

## 2. Microsoft Azure

### 2.1 Azure hierarchy and governance

Azure uses a hierarchy of **Management Groups > Subscriptions > Resource Groups > Resources**.

| Object | Purpose | Best practice |
|---|---|---|
| Management group | Policy and RBAC inheritance across subscriptions | Use for environment, business unit, or landing-zone boundaries |
| Subscription | Billing, access, policy, and resource boundary | Separate production, non-production, and platform workloads |
| Resource group | Logical deployment and lifecycle container | Group resources with the same lifecycle |
| Resource | Deployable Azure object | Tag, secure, monitor, and back up as required |
| Azure Policy | Governance and compliance enforcement | Apply at management-group or subscription scope |
| Azure RBAC | Role-based access control | Assign roles to groups, not individual users |

**Azure RBAC roles commonly used:**

| Role | Typical use |
|---|---|
| Owner | Full control including access assignment; restrict to break-glass or platform owners |
| Contributor | Create and manage resources; cannot assign RBAC |
| Reader | View-only access |
| Network Contributor | Manage networking resources |
| Virtual Machine Contributor | Manage VMs but not the VNet they attach to |
| Key Vault Secrets User | Read secrets; do not grant broad Key Vault access |
| Backup Contributor | Configure backups |
| Cost Management Contributor | View and manage cost data |

**Azure CLI examples:**

```bash
# Read-only: list subscriptions
az account list --output table

# Read-only: list resource groups
az group list --output table

# Modifying: create a resource group
az group create --name rg-prod-weu-core --location westeurope

# Read-only: list VMs
az vm list --output table

# Modifying: start a VM
az vm start --resource-group <resource-group> --name <vm-name>

# Modifying: deallocate a VM
az vm deallocate --resource-group <resource-group> --name <vm-name>
```

**Safety:** `az vm deallocate` stops billing for compute but retains disks, IP addresses, and other billable resources. It does not delete the VM.

### 2.2 Azure networking

| Component | Purpose |
|---|---|
| Virtual network (VNet) | Private network boundary in Azure |
| Subnet | Segment within a VNet for workloads and services |
| Network Security Group (NSG) | Stateful L3/L4 traffic rules |
| Azure Firewall | Managed centralized firewall with threat intelligence and FQDN filtering |
| Azure Bastion | Browser-based private RDP/SSH access |
| Private Endpoint | Private access to PaaS services through a private IP |
| Private Link | Private connectivity service enabling private endpoints |
| ExpressRoute | Private dedicated connectivity between on-premises and Azure |
| VPN Gateway | Encrypted site-to-site or point-to-site connectivity |
| Load Balancer | Layer 4 load balancing |
| Application Gateway | Layer 7 load balancing, WAF, SSL termination |
| Azure DNS | Public and private DNS zones |

**Recommended hub-and-spoke pattern:**

```text
On-premises data center
        |
  ExpressRoute / Site-to-Site VPN
        |
   Azure Hub VNet
   - Azure Firewall
   - VPN/ExpressRoute Gateway
   - DNS resolvers
   - Shared services
        |
  -------------------------
  |           |           |
Spoke VNet   Spoke VNet  Spoke VNet
App team A   App team B  Kubernetes
```

**NSG design rules:**

- Deny inbound Internet access to workload subnets unless explicitly required.
- Allow management access only from approved jump hosts, Bastion, or private management ranges.
- Use service tags such as `VirtualNetwork`, `AzureLoadBalancer`, and `AzureKeyVault` where appropriate.
- Apply NSGs at subnet level for broad segmentation and NIC level for host-specific exceptions.
- Log NSG flow logs to Log Analytics for investigation.

**Azure CLI networking examples:**

```bash
# Read-only: list VNets
az network vnet list --output table

# Modifying: create a VNet and subnet
az network vnet create \
  --resource-group <resource-group> \
  --name <vnet-name> \
  --address-prefix <cidr> \
  --subnet-name <subnet-name> \
  --subnet-prefix <subnet-cidr>

# Read-only: show effective NSG rules
az network nic list-effective-nsg \
  --resource-group <resource-group> \
  --name <nic-name>
```

### 2.3 Azure compute and storage

**Azure Virtual Machines:**

- Use availability zones for zonal resilience where the region supports them.
- Use VM Scale Sets or AKS for elastic workloads.
- Use managed disks; separate OS and data disks where appropriate.
- Enable Azure Backup and disk encryption.
- Use managed identities instead of stored credentials where supported.
- Apply Azure Update Manager or a supported patching process.

**Azure Storage:**

| Service | Use case |
|---|---|
| Blob Storage | Object data, backups, logs, media |
| File Shares | SMB file shares, lift-and-shift file workloads |
| Queue Storage | Message queuing |
| Table Storage | Structured NoSQL data |
| Managed Disks | VM disks |
| Azure Files | Fully managed SMB/NFS file shares |

**Storage security controls:**

- Disable public blob access unless explicitly justified.
- Use Private Endpoints for sensitive storage.
- Use Azure AD/Entra ID-based authorization where supported.
- Enable soft delete, versioning, immutability policies, and lifecycle management where appropriate.
- Use customer-managed keys only when business or compliance requirements justify the operational overhead.

### 2.4 Azure identity and security

**Microsoft Entra ID** is the identity plane for Azure, Microsoft 365, and many SaaS applications.

Key controls:

- Require MFA for all privileged and remote-access users.
- Use Conditional Access based on user risk, device compliance, location, and application sensitivity.
- Use Privileged Identity Management for just-in-time elevated access.
- Use managed identities for Azure resources rather than service-principal secrets.
- Store secrets in Azure Key Vault.
- Enable diagnostic logging for Entra ID sign-ins and audit events.
- Use PIM or equivalent approval workflows for privileged roles.

**Azure Policy examples:**

| Policy intent | Example control |
|---|---|
| Restrict regions | Allow deployment only in approved regions |
| Require tags | Require `owner`, `environment`, `cost-center`, and `application` tags |
| Require encryption | Require encryption on storage accounts and disks |
| Restrict public access | Deny public network access to sensitive PaaS services |
| Require backup | Audit or deploy backup protection for VMs |

### 2.5 Azure Kubernetes Service

AKS is a managed Kubernetes control plane. Customers remain responsible for workload security, node configuration where applicable, identity, networking policies, upgrades, and operational practices.

Recommended baseline:

- Use Azure CNI or CNI Overlay according to IP and networking requirements.
- Use private API server endpoints for sensitive environments.
- Use Azure RBAC and Entra ID integration for cluster access.
- Use managed identities or workload identity federation for pod-to-Azure access.
- Use Azure Policy for AKS to enforce security baselines.
- Use node pools separated by workload criticality and operating system.
- Enable cluster and control-plane diagnostics to Log Analytics.
- Use Kubernetes Network Policies for east-west segmentation.

## 3. Amazon Web Services

### 3.1 AWS account structure

AWS Organizations enables multi-account governance.

| Structure | Purpose |
|---|---|
| Management account | Organization administration; avoid deploying workloads here |
| Security Tooling account | Security tooling, audit logs, GuardDuty, Security Hub |
| Log Archive account | Immutable centralized audit and log storage |
| Shared Services account | Shared networking, DNS, monitoring, and operational tooling |
| Workload accounts | Isolated production and non-production workloads |
| Sandbox accounts | Experimentation with spend and access limits |

**AWS IAM principles:**

- Use IAM Identity Center for human access where possible.
- Use IAM roles, not long-lived IAM users, for workloads.
- Use permission boundaries and SCPs for guardrails.
- Require MFA for privileged access.
- Avoid wildcard `Action: "*"` and `Resource: "*"` unless justified and reviewed.
- Use session policies and role assumption for temporary access.

**AWS CLI examples:**

```bash
# Read-only: identify current identity
aws sts get-caller-identity

# Read-only: list S3 buckets
aws s3 ls

# Read-only: describe EC2 instances
aws ec2 describe-instances \
  --filters "Name=instance-state-name,Values=running" \
  --query "Reservations[].Instances[].{ID:InstanceId,Name:Tags[?Key=='Name']|[0].Value,Type:InstanceType}" \
  --output table

# Modifying: start an EC2 instance
aws ec2 start-instances --instance-ids <instance-id>

# Modifying: stop an EC2 instance
aws ec2 stop-instances --instance-ids <instance-id>
```

### 3.2 AWS networking

| Component | Purpose |
|---|---|
| VPC | Isolated virtual network |
| Subnet | Network segment, public or private |
| Route table | Routing rules |
| Internet Gateway | Public Internet access for public subnets |
| NAT Gateway | Outbound Internet access for private subnets |
| Security Group | Stateful instance-level firewall |
| Network ACL | Stateless subnet-level firewall |
| Transit Gateway | Hub for VPC and on-premises connectivity |
| Direct Connect | Dedicated private connectivity |
| Site-to-Site VPN | Encrypted IPsec connectivity |
| Route 53 | DNS service |
| ELB / ALB / NLB | Elastic, application, and network load balancing |

**Security Group versus NACL:**

| Attribute | Security Group | Network ACL |
|---|---|---|
| Scope | Instance/ENI | Subnet |
| State | Stateful | Stateless |
| Rule evaluation | All rules evaluated | Rules evaluated in numbered order |
| Typical use | Workload access control | Coarse subnet segmentation |

### 3.3 AWS storage and backup

| Service | Use case |
|---|---|
| EBS | Block storage for EC2 |
| S3 | Object storage |
| EFS | Shared POSIX file system |
| FSx | Managed Windows File Server, NetApp ONTAP, OpenZFS, or Lustre |
| AWS Backup | Centralized backup policy and recovery |
| S3 Glacier | Archival storage classes |

**AWS Backup design:**

- Define backup plans by workload criticality.
- Use backup vaults with access controls and, where required, immutability.
- Use cross-region backup copies for DR.
- Test restores regularly; a backup that has not been restored is unverified.
- Monitor backup jobs, retention, and failed recovery points.

### 3.4 AWS monitoring and migration

**CloudWatch** provides metrics, logs, alarms, dashboards, and event-based automation. **CloudTrail** records API activity for audit and investigation.

**AWS migration services:**

| Service | Use |
|---|---|
| AWS Migration Hub | Central migration tracking |
| AWS Application Discovery Service | Discovery and dependency assessment |
| AWS DMS | Database migration |
| AWS SCT | Schema and code conversion assessment |
| AWS DataSync | Data transfer |
| AWS Transfer Family | Managed file transfer |
| AWS EBS direct snapshots / VM Import | VM-based migration paths |

### 3.5 Amazon EKS

EKS is a managed Kubernetes control plane. Recommended practices:

- Use private endpoint access for production clusters.
- Use IAM Roles for Service Accounts (IRSA) or EKS Pod Identity where appropriate.
- Use separate node groups for system, general, and high-performance workloads.
- Enable Control Plane logging to CloudWatch.
- Use security groups for pods where applicable.
- Use AWS Load Balancer Controller for ingress.
- Use Karpenter or Cluster Autoscaler for capacity management.

## 4. Google Cloud Platform

### 4.1 GCP resource hierarchy

GCP uses **Organization > Folders > Projects > Resources**.

| Object | Purpose |
|---|---|
| Organization | Top-level enterprise boundary |
| Folder | Grouping for teams, environments, or business units |
| Project | Resource, billing, API, and IAM boundary |
| Resource | Deployable GCP object |
| Organization Policy | Guardrails inherited down the hierarchy |
| Cloud IAM | Identity and access management |

**Recommended project design:**

- `host-project` for shared VPC and networking.
- `logging-project` for centralized logs and monitoring.
- `security-project` for security tooling.
- Separate projects for production, staging, development, and shared services.
- Avoid using one project for all workloads.

### 4.2 GCP networking

| Component | Purpose |
|---|---|
| VPC | Global or regional virtual network |
| Subnet | Regional IP range |
| Firewall rule | VPC-level traffic control |
| Cloud NAT | Outbound Internet access for private instances |
| Cloud VPN | IPsec connectivity |
| Cloud Interconnect | Dedicated private connectivity |
| Private Service Connect | Private access to managed services |
| Cloud Load Balancing | Global or regional load balancing |
| Cloud DNS | Managed DNS |

**GCP firewall rules are VPC-level**, unlike AWS Security Groups which attach to ENIs. Use network tags, service accounts, or IP ranges as the source/target selectors.

**gcloud examples:**

```bash
# Read-only: list projects
gcloud projects list

# Read-only: list compute instances
gcloud compute instances list

# Modifying: create a VPC subnet
gcloud compute networks subnets create <subnet-name> \
  --network <vpc-name> \
  --region <region> \
  --range <cidr>

# Read-only: describe an instance
gcloud compute instances describe <instance-name> \
  --zone <zone>
```

### 4.3 GCP storage, compute, and Kubernetes

| Service | Use case |
|---|---|
| Compute Engine | Virtual machines |
| Persistent Disk | Block storage |
| Cloud Storage | Object storage |
| Filestore | Managed NFS |
| Cloud SQL | Managed relational databases |
| AlloyDB | PostgreSQL-compatible managed database |
| BigQuery | Analytics warehouse |
| GKE | Managed Kubernetes |
| Backup and DR Service | Backup and recovery |
| Security Command Center | Security posture and threat detection |

**GKE recommendations:**

- Use private clusters for production.
- Use Workload Identity Federation instead of exported service-account keys.
- Use Binary Authorization for supply-chain controls where required.
- Enable GKE audit logs and Cloud Logging.
- Use separate node pools for system and application workloads.
- Use Network Policy for namespace and workload segmentation.

## 5. Windows Server administration

### 5.1 Windows Server versions

| Version | Support status guidance |
|---|---|
| Windows Server 2016 | Older release; validate extended support and security posture |
| Windows Server 2019 | Common enterprise baseline |
| Windows Server 2022 | Current common enterprise baseline |
| Windows Server 2025 | Newer release; validate application and agent compatibility |

Support dates and lifecycle status change; always validate against the Microsoft Lifecycle Policy before planning upgrades or migrations.

### 5.2 Active Directory Domain Services

Active Directory Domain Services provides directory, authentication, authorization, DNS, Group Policy, and domain services.

**Core components:**

- Domain controllers
- Active Directory database: `NTDS.dit`
- SYSVOL
- Kerberos and NTLM authentication
- DNS
- Group Policy
- Organizational Units
- FSMO roles

**FSMO roles:**

| Role | Scope | Purpose |
|---|---|---|
| Schema Master | Forest | Schema changes |
| Domain Naming Master | Forest | Domain add/remove |
| PDC Emulator | Domain | Time, password changes, legacy compatibility |
| RID Master | Domain | Relative ID allocation |
| Infrastructure Master | Domain | Cross-domain object references |

**PowerShell examples:**

```powershell
# Read-only: identify domain controllers
Get-ADDomainController -Filter *

# Read-only: identify FSMO role holders
Get-ADForest | Select-Object SchemaMaster, DomainNamingMaster
Get-ADDomain | Select-Object PDCEmulator, RIDMaster, InfrastructureMaster

# Read-only: check AD replication health
repadmin /replsummary

# Read-only: force replication knowledge consistency check
repadmin /kcc *

# Modifying: create an organizational unit
New-ADOrganizationalUnit -Name "Servers" -Path "DC=<domain>,DC=<local>"

# Modifying: create a user
New-ADUser -Name "<username>" `
  -SamAccountName "<username>" `
  -UserPrincipalName "<username>@<domain>" `
  -Path "OU=Users,DC=<domain>,DC=<local>" `
  -AccountPassword (Read-Host -AsSecureString "Password") `
  -Enabled $true
```

### 5.3 DNS, DHCP, Group Policy, and file services

**DNS:**

- Use AD-integrated DNS for domain controllers.
- Ensure clients use reliable internal DNS servers.
- Use conditional forwarders for hybrid or multi-domain resolution.
- Monitor DNS event logs and scavenging configuration.

**DHCP:**

- Use authorized Windows DHCP servers or a supported network DHCP service.
- Reserve addresses for infrastructure systems.
- Monitor scope utilization and conflicts.
- Ensure DHCP option 006 points to correct DNS servers.

**Group Policy:**

- Link GPOs at the narrowest effective OU scope.
- Use security filtering and WMI filtering carefully.
- Test with `gpresult` and Group Policy Modeling.
- Maintain change control for GPO modifications.

```powershell
# Read-only: apply Group Policy results for current user and computer
gpresult /h C:\Temp\gpreport.html

# Read-only: list applied GPOs
gpresult /r

# Modifying: force Group Policy refresh
gpupdate /force
```

**File server permissions:**

| Layer | Best practice |
|---|---|
| NTFS | Use security groups, not individual users |
| Share permissions | Keep broad; enforce detailed control through NTFS |
| Inheritance | Disable only when a deliberate exception is required |
| Ownership | Assign a known administrative owner |
| Auditing | Enable access auditing for sensitive shares |

### 5.4 IIS, clustering, Hyper-V, and hardening

**IIS:**

- Run application pools under least-privilege identities.
- Use separate application pools per application where practical.
- Enable HTTPS with valid certificates.
- Restrict remote administration.
- Monitor worker-process recycling, CPU, memory, and failed requests.

**Failover Clustering:**

- Validate storage, networking, quorum, and application compatibility.
- Use node majority or appropriate quorum configuration.
- Test controlled failover before relying on it in production.
- Monitor cluster events and node health.

**Hyper-V:**

- Keep hosts, integration services, and virtual machines patched.
- Use separate management, storage, live-migration, and workload VLANs where appropriate.
- Protect host configuration and VM checkpoints.
- Validate backup compatibility with the hypervisor and guest OS.

**Windows hardening checklist:**

- Disable or restrict unused local accounts.
- Enforce complex passwords and MFA for administrative access.
- Restrict RDP to approved networks and use NLA.
- Enable Windows Defender Firewall with documented exceptions.
- Enable BitLocker or equivalent disk encryption where supported.
- Enable audit policies for logon, privilege use, and object access.
- Use Windows Defender or approved EDR.
- Restrict PowerShell execution policy and enable script-block logging where appropriate.
- Remove legacy protocols such as SMBv1 unless required.

### 5.5 Windows troubleshooting

```powershell
# Read-only: system information
Get-ComputerInfo

# Read-only: running services
Get-Service | Where-Object Status -eq 'Running'

# Read-only: recent system events
Get-WinEvent -LogName System -MaxEvents 50

# Read-only: recent application events
Get-WinEvent -LogName Application -MaxEvents 50

# Read-only: network configuration
Get-NetIPConfiguration
Get-NetAdapter
Get-NetRoute

# Read-only: test DNS resolution
Resolve-DnsName <hostname>

# Read-only: test TCP port
Test-NetConnection -ComputerName <hostname> -Port <port>

# Read-only: disk usage
Get-PSDrive -PSProvider FileSystem

# Read-only: top processes by CPU
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10
```

## 6. Linux server administration

### 6.1 Supported distributions

| Distribution | Package manager | Init system | Typical enterprise use |
|---|---|---|---|
| Ubuntu Server | APT | systemd | Cloud, web, DevOps |
| Debian | APT | systemd | Stable infrastructure |
| RHEL | DNF/YUM | systemd | Enterprise production |
| Rocky Linux | DNF/YUM | systemd | RHEL-compatible replacement |
| AlmaLinux | DNF/YUM | systemd | RHEL-compatible replacement |
| SUSE Linux Enterprise | Zypper | systemd | Enterprise and SAP workloads |
| Amazon Linux | DNF/YUM depending on version | systemd | AWS-native workloads |

### 6.2 Users, SSH, sudo, and permissions

```bash
# Read-only: current identity
whoami
id

# Read-only: list users
cat /etc/passwd

# Read-only: list groups
cat /etc/group

# Modifying: create a user
sudo useradd -m -s /bin/bash <username>

# Modifying: set a password
sudo passwd <username>

# Modifying: add user to sudo group on Ubuntu/Debian
sudo usermod -aG sudo <username>

# Modifying: add user to wheel group on RHEL-family systems
sudo usermod -aG wheel <username>

# Read-only: view sudo rules
sudo -l
```

**SSH hardening:**

- Disable direct root SSH login where possible.
- Use key-based authentication.
- Restrict SSH to required users or groups.
- Change the default port only if it provides a documented operational benefit; it is not a security control by itself.
- Enable `AllowTcpForwarding no` for restricted jump hosts where appropriate.
- Use fail2ban, firewall rules, or cloud-native controls to limit brute-force exposure.

```bash
# Read-only: test SSH connectivity
ssh -v <user>@<hostname>

# Read-only: show effective SSH configuration
sudo sshd -T | grep -E 'PermitRootLogin|PasswordAuthentication|PubkeyAuthentication'

# Modifying: restart SSH service
sudo systemctl restart sshd
```

### 6.3 Storage, LVM, filesystems, and expansion

```bash
# Read-only: list block devices
lsblk

# Read-only: show mounted filesystems and usage
df -h

# Read-only: show disk usage by directory
sudo du -sh /var/* 2>/dev/null | sort -h

# Read-only: list physical volumes
sudo pvs

# Read-only: list volume groups
sudo vgs

# Read-only: list logical volumes
sudo lvs

# Modifying: extend a logical volume
sudo lvextend -l +100%FREE /dev/<vg-name>/<lv-name>

# Modifying: grow an ext4 filesystem
sudo resize2fs /dev/<vg-name>/<lv-name>

# Modifying: grow an XFS filesystem
sudo xfs_growfs /<mount-point>
```

**Important:** Identify the filesystem type before resizing. `resize2fs` is for ext-family filesystems; `xfs_growfs` is for XFS. Verify the device path before executing modifying commands.

### 6.4 Networking, firewall, SELinux, and services

```bash
# Read-only: interfaces and addresses
ip addr

# Read-only: routing table
ip route

# Read-only: listening ports
sudo ss -tulnp

# Read-only: DNS resolution
dig <hostname>
nslookup <hostname>

# Read-only: trace route
traceroute <hostname>

# Read-only: firewall status
sudo ufw status verbose                 # Ubuntu/Debian with UFW
sudo firewall-cmd --list-all            # RHEL-family with firewalld

# Modifying: allow SSH with UFW
sudo ufw allow 22/tcp

# Modifying: allow HTTPS with firewalld
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

**SELinux:**

```bash
# Read-only: current SELinux mode
getenforce

# Read-only: SELinux context
ls -Z /var/www/html

# Read-only: SELinux denials
sudo ausearch -m avc -ts recent

# Modifying: restore default context
sudo restorecon -Rv /var/www/html
```

Do not set SELinux to permissive as a permanent production solution. Identify the denial, apply the correct policy or context, then return to enforcing mode.

### 6.5 Logs, performance, patching, and scheduling

```bash
# Read-only: recent system logs
sudo journalctl -xe

# Read-only: logs for a service
sudo journalctl -u <service-name> -n 100

# Read-only: CPU and memory
top
free -h

# Read-only: disk I/O
iostat -xz 1 5

# Read-only: network connections
sudo ss -s

# Modifying: update packages on Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# Modifying: update packages on RHEL-family systems
sudo dnf upgrade -y

# Modifying: create a scheduled job
sudo crontab -e
```

**Cron format:**

```text
minute hour day-of-month month day-of-week command
```

Example: run a script daily at 02:30.

```text
30 2 * * * /opt/scripts/backup.sh >> /var/log/backup.log 2>&1
```

## 7. Cloud architecture and solution design

### 7.1 Landing zones

A landing zone provides a governed foundation for cloud adoption.

**Business requirement:** Enable multiple teams to deploy workloads securely, consistently, and cost-effectively.

**Technical requirements:**

- Centralized identity and access management
- Hub-and-spoke or equivalent network segmentation
- Centralized logging and monitoring
- Policy-as-code guardrails
- Standardized tagging
- Backup and DR baseline
- Cost allocation and budget controls
- Automation and CI/CD integration

**Azure implementation:**

- Management groups for platform, landing zones, and decommissioned zones.
- Separate subscriptions for connectivity, identity, management, and workloads.
- Azure Policy for required tags, allowed regions, encryption, and public-access restrictions.
- Azure Firewall, Private DNS, Bastion, and centralized Log Analytics in platform subscriptions.

**AWS implementation:**

- AWS Organizations with security, log-archive, shared-services, and workload accounts.
- IAM Identity Center for human access.
- SCPs for guardrails.
- Centralized CloudTrail, Config, GuardDuty, Security Hub, and CloudWatch cross-account observability.
- Transit Gateway or AWS Network Firewall for shared networking.

**GCP implementation:**

- Organization, folders, and projects aligned to environment and application ownership.
- Shared VPC host and service projects.
- Organization policies for domain restriction, service usage, and resource location.
- Centralized Cloud Logging, Monitoring, Security Command Center, and billing export.

### 7.2 Hub-and-spoke networking

**Business requirement:** Isolate application teams while sharing connectivity, security, and operational services.

**Architecture:**

- Hub VNet/VPC contains shared security and connectivity services.
- Spokes contain application workloads.
- Peering or Transit Gateway connects spokes to the hub.
- East-west traffic can be inspected through a firewall or NVA where required.
- Private DNS resolves internal service names.
- No direct spoke-to-spoke connectivity unless explicitly required.

**Security controls:**

- Default-deny inbound from Internet.
- Restrict management ports to approved sources.
- Use private endpoints for PaaS services.
- Enable flow logs and firewall logs.
- Segment production from non-production.

### 7.3 High availability and disaster recovery

| Pattern | Description | Typical use |
|---|---|---|
| Active-passive | Standby environment activated during failure | Cost-sensitive DR |
| Active-active | Multiple regions serve traffic simultaneously | Low-latency global applications |
| Pilot light | Minimal core environment always running | Moderate RTO |
| Warm standby | Scaled-down full environment running | Faster RTO |
| Multi-site active-active | Full capacity in multiple regions | Mission-critical workloads |

**Design questions:**

- What is the acceptable RPO?
- What is the acceptable RTO?
- Which dependencies must fail over?
- Is data replication synchronous or asynchronous?
- What is the DNS and traffic-management failover approach?
- Has recovery been tested end to end?

## 8. Cloud migration

### 8.1 Migration lifecycle

1. **Discovery:** Inventory servers, applications, databases, dependencies, integrations, and data.
2. **Assessment:** Evaluate performance, capacity, compatibility, security, licensing, and migration readiness.
3. **Strategy:** Select the appropriate migration approach for each workload.
4. **Planning:** Define waves, cutover, rollback, testing, and communication.
5. **Pilot:** Migrate low-risk workloads to validate tooling and process.
6. **Migration waves:** Execute in controlled groups.
7. **Cutover:** Move production traffic with validation and rollback readiness.
8. **Hypercare:** Provide intensive operational support after go-live.
9. **Handover:** Transfer documentation, access, monitoring, and operational ownership.

### 8.2 The 7 Rs

| Strategy | Meaning | Example |
|---|---|---|
| Rehost | Lift and shift without major change | VMware VM moved to Azure VM |
| Replatform | Minor optimization without core redesign | Move database to managed database service |
| Refactor | Modify application architecture | Split monolith into microservices |
| Repurchase | Replace with SaaS | Replace self-hosted CRM with SaaS |
| Retire | Decommission unused workload | Shut down obsolete legacy server |
| Retain | Keep on-premises for now | Latency- or compliance-bound system |
| Relocate | Move hypervisor or platform without changing VMs | VMware Cloud on AWS or Azure VMware Solution |

### 8.3 Migration assessment checklist

- [ ] Application name, owner, business criticality, and environment
- [ ] Operating system, version, patch level, and end-of-support status
- [ ] CPU, memory, disk, IOPS, throughput, and network utilization
- [ ] Peak and average utilization
- [ ] Application dependencies and ports
- [ ] Database type, version, size, and licensing
- [ ] Certificates, service accounts, scheduled jobs, and integrations
- [ ] Backup and recovery requirements
- [ ] Compliance, residency, and data-classification requirements
- [ ] Downtime tolerance and maintenance window
- [ ] Rollback plan
- [ ] Post-migration validation criteria

### 8.4 Migration runbook template

```text
Migration Runbook: <Application or Server>

1. Objective
2. Scope
3. Preconditions
4. Roles and responsibilities
5. Communication plan
6. Pre-cutover checklist
7. Migration steps
8. Validation steps
9. Rollback steps
10. Hypercare actions
11. Approval record
```

### 8.5 Scenario A: VMware to Azure migration

**Requirement:** Migrate 200 Windows and Linux servers from VMware to Azure with minimal downtime.

**Approach:**

- Use Azure Migrate for discovery, assessment, and replication.
- Group servers into migration waves based on dependency and criticality.
- Use test migrations before production cutover.
- Replicate data ahead of cutover where supported.
- Perform final synchronization during the approved maintenance window.
- Validate application functionality, performance, DNS, certificates, backup, and monitoring.
- Retain the source environment until hypercare completes.

**Validation checklist:**

- [ ] VM boots successfully
- [ ] IP addressing and DNS are correct
- [ ] Domain join and authentication work
- [ ] Required services are running
- [ ] Application endpoints respond
- [ ] Certificates are valid
- [ ] Backups are configured
- [ ] Monitoring agents report correctly
- [ ] Performance meets baseline
- [ ] Rollback remains possible

## 9. Networking fundamentals

### 9.1 TCP/IP and OSI

| OSI layer | Examples |
|---|---|
| 1 Physical | Cabling, optical links |
| 2 Data link | MAC, Ethernet, VLAN |
| 3 Network | IP, routing, ICMP |
| 4 Transport | TCP, UDP, ports |
| 5 Session | Session establishment |
| 6 Presentation | Encoding, encryption |
| 7 Application | HTTP, DNS, SMTP, RDP, SSH |

### 9.2 Subnetting

CIDR notation defines the prefix length.

| CIDR | Host addresses | Usable hosts for general IPv4 subnet |
|---|---:|---:|
| /24 | 256 | 254 |
| /25 | 128 | 126 |
| /26 | 64 | 62 |
| /27 | 32 | 30 |
| /28 | 16 | 14 |
| /29 | 8 | 6 |
| /30 | 4 | 2 |

Example: `10.20.30.0/24` contains addresses `10.20.30.0` through `10.20.30.255`.

### 9.3 Network troubleshooting

```bash
# Linux and Windows-compatible tools vary by OS
ping <hostname-or-IP>
traceroute <hostname-or-IP>       # Linux/macOS
tracert <hostname-or-IP>          # Windows
nslookup <hostname>               # Windows/Linux
dig <hostname>                    # Linux
```

**Windows:**

```powershell
ipconfig /all
route print
Get-NetIPConfiguration
Test-NetConnection -ComputerName <hostname> -Port <port>
Resolve-DnsName <hostname>
tracert <hostname>
```

**Linux:**

```bash
ip addr
ip route
ss -tulnp
dig <hostname>
traceroute <hostname>
curl -vk https://<hostname>
```

## 10. Security and identity

### 10.1 Zero Trust principles

- Verify explicitly.
- Use least-privilege access.
- Assume breach.
- Segment networks and workloads.
- Continuously monitor and validate.
- Protect secrets and privileged access.

### 10.2 Identity checklist

- [ ] MFA enforced for administrators
- [ ] Privileged roles require approval or just-in-time activation
- [ ] Break-glass accounts are protected and monitored
- [ ] Service accounts use managed identities or short-lived credentials where possible
- [ ] Secrets are stored in a managed secret store
- [ ] Certificates have expiry monitoring
- [ ] Access reviews are scheduled
- [ ] Privileged sessions are logged
- [ ] Legacy authentication is restricted where possible

### 10.3 Incident response

1. Detect and triage.
2. Contain the impact.
3. Preserve evidence.
4. Eradicate the threat.
5. Recover services.
6. Conduct post-incident review.
7. Implement preventive actions.

**Incident severity example:**

| Severity | Definition | Initial response |
|---|---|---|
| P1 | Critical production outage or security breach | Immediate escalation and incident bridge |
| P2 | Major degradation with business impact | Urgent response |
| P3 | Limited impact or non-production issue | Scheduled response |
| P4 | Low-impact request or informational issue | Standard queue |

## 11. Automation and IaC

### 11.1 Tool selection

| Tool | Best use |
|---|---|
| PowerShell | Windows automation, Azure administration |
| Bash | Linux automation and operational scripting |
| Python | APIs, orchestration, reporting, custom integrations |
| Terraform | Multi-cloud declarative IaC |
| Ansible | Configuration management and orchestration |
| Bicep | Azure-native declarative IaC |
| ARM templates | Azure resource deployment |
| CloudFormation | AWS-native declarative IaC |
| AWS CDK | AWS infrastructure using programming languages |
| Git | Version control and peer review |
| CI/CD | Automated validation and deployment |

### 11.2 Terraform example

```hcl
resource "azurerm_resource_group" "example" {
  name     = "<resource-group-name>"
  location = "<azure-region>"
}

resource "azurerm_virtual_network" "example" {
  name                = "<vnet-name>"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
  address_space       = ["<cidr>"]
}
```

**Safety:** Terraform can destroy and recreate resources. Always run `terraform plan`, review the plan, use remote state with locking, and restrict state access.

### 11.3 Ansible example

```yaml
- name: Ensure NTP service is running
  hosts: linux_servers
  become: true
  tasks:
    - name: Install chrony
      ansible.builtin.package:
        name: chrony
        state: present

    - name: Enable and start chrony
      ansible.builtin.service:
        name: chronyd
        enabled: true
        state: started
```

## 12. Monitoring and troubleshooting

### 12.1 VM unavailable

| Item | Details |
|---|---|
| Symptoms | No RDP/SSH, application unavailable, monitoring agent offline |
| Possible causes | VM stopped, OS boot failure, network misconfiguration, NSG/Security Group block, firewall, disk issue, authentication issue |
| Diagnostics | Check cloud console state, boot diagnostics, serial console, NSG/Security Group rules, route tables, OS logs |
| Resolution | Start VM, repair boot issue, correct network rule, restore from backup if needed |
| Validation | Confirm connectivity, service health, monitoring, and application response |
| Prevention | Health probes, alerting, backup, change control, documented recovery |

### 12.2 High CPU or disk I/O

**Linux:**

```bash
top
pidstat -u 1 5
iostat -xz 1 5
vmstat 1 5
```

**Windows:**

```powershell
Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 2 -MaxSamples 5
Get-Counter '\PhysicalDisk(_Total)\Avg. Disk sec/Transfer' -SampleInterval 2 -MaxSamples 5
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10
```

### 12.3 DNS resolution failure

**Symptoms:** Name resolution fails, applications cannot reach dependencies, intermittent failures.

**Diagnostics:**

```bash
# Linux
dig <hostname>
dig @<dns-server> <hostname>
resolvectl status

# Windows
Resolve-DnsName <hostname>
nslookup <hostname>
ipconfig /displaydns
```

**Resolution options:**

- Correct DNS server configuration.
- Correct DNS records.
- Fix VPC/VNet DNS settings.
- Validate private DNS zones and endpoints.
- Check firewall access to DNS servers.

## 13. Backup, HA, and disaster recovery

### 13.1 Backup principles

- Define RPO and RTO before selecting technology.
- Use application-consistent backups for databases and transactional applications where supported.
- Use crash-consistent backups only when acceptable for the workload.
- Separate backup credentials and access from production administration.
- Use immutability or object lock where compliance and recovery requirements demand it.
- Test restores, not merely backup job success.

### 13.2 DR runbook template

```text
Disaster Recovery Runbook

1. Declaration criteria
2. Incident commander and contacts
3. impacted systems
4. Dependencies
5. Failover procedure
6. DNS and traffic redirection
7. Validation checklist
8. Communication plan
9. Failback procedure
10. Rollback procedure
```

## 14. Documentation templates

### 14.1 High-Level Design template

```text
# High-Level Design

1. Document control
2. Purpose
3. Scope
4. Business requirements
5. Technical requirements
6. Assumptions
7. Constraints
8. Architecture overview
9. Network design
10. Identity and access design
11. Security controls
12. Availability and DR
13. Monitoring
14. Cost considerations
15. Implementation approach
16. Operational model
17. Risks
18. Approvals
```

### 14.2 Risk register template

| ID | Risk | Impact | Likelihood | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|
| R-001 | Data loss during migration | High | Medium | Backup, test restore, rollback plan | Migration lead | Open |

## 15. ITSM and operations

### 15.1 Incident management

- Detect through monitoring or user report.
- Categorize and prioritize.
- Assign ownership.
- Communicate status.
- Restore service.
- Document root cause.
- Conduct post-incident review.

### 15.2 Change management

- Define change type: standard, normal, or emergency.
- Document risk, impact, implementation, validation, and rollback.
- Obtain approval according to policy.
- Schedule during approved windows.
- Validate after implementation.
- Close with evidence and documentation.

## 16. FinOps and cost optimization

### 16.1 Cost controls

| Control | Purpose |
|---|---|
| Tagging | Cost allocation and ownership |
| Budgets and alerts | Prevent uncontrolled spend |
| Rightsizing | Match capacity to demand |
| Reserved capacity | Reduce cost for predictable usage |
| Savings plans | Flexible commitment-based discounts |
| Autoscaling | Match capacity to workload |
| Scheduled shutdown | Reduce non-production waste |
| Storage lifecycle | Move cold data to lower-cost tiers |
| Reserved IP cleanup | Remove unused addresses |

### 16.2 Monthly cost report template

| Workload | Owner | Environment | Current spend | Forecast | Budget | Variance | Action |
|---|---|---|---:|---:|---:|---:|---|
| Application A | Team A | Production | <value> | <value> | <value> | <value> | Review |

## 17. Practical scenarios

### Scenario B: Hybrid cloud network

**Requirement:** Connect an on-premises data center to Azure and AWS securely.

**Architecture:**

- ExpressRoute or VPN for Azure.
- Direct Connect or Site-to-Site VPN for AWS.
- Hub networks in each cloud.
- Transit Gateway in AWS and hub VNet in Azure.
- Firewall inspection for Internet and cross-cloud traffic where required.
- Private DNS forwarding between environments.
- Separate production and non-production routing.

**Validation:**

- [ ] BGP or static routes established
- [ ] On-premises to cloud connectivity verified
- [ ] Cloud-to-cloud routing verified if required
- [ ] DNS resolution verified
- [ ] Firewall policies tested
- [ ] Failover tested
- [ ] Monitoring and alerts operational

### Scenario C: Active Directory architecture

**Requirement:** Maintain identity services across on-premises and cloud.

**Architecture:**

- At least two domain controllers on-premises.
- At least two domain controllers in cloud, placed in separate availability zones or regions where supported.
- AD-integrated DNS.
- Secure replication paths.
- Time synchronization from reliable sources.
- Backup of system state and AD database where supported.
- Monitoring for replication, authentication, DNS, and disk health.

### Scenario D: Windows VM reachable by RDP but application unavailable

**Diagnostic sequence:**

1. Confirm RDP connectivity.
2. Check application service status.
3. Review Application and System event logs.
4. Check application port listening status.
5. Test local application endpoint.
6. Check firewall rules.
7. Review certificate validity.
8. Review dependency connectivity.
9. Review recent changes.
10. Restart service only after impact assessment.

```powershell
Get-Service <service-name>
Test-NetConnection -ComputerName localhost -Port <port>
Get-EventLog -LogName Application -Newest 50
```

### Scenario E: Linux VM high CPU and disk I/O

```bash
top
pidstat -u 1 5
iostat -xz 1 5
df -h
sudo journalctl -xe
```

**Typical causes:**

- Runaway process
- Insufficient capacity
- Disk saturation
- Logging storm
- Malware or cryptomining
- Application bug
- Backup or antivirus scan

## 18. Command reference safety

| Command type | Risk | Safety control |
|---|---|---|
| `az vm deallocate` | Stops VM compute | Confirm VM name and resource group |
| `aws ec2 terminate-instances` | Deletes EC2 instances | Require explicit approval |
| `gcloud compute instances delete` | Deletes compute instances | Require explicit approval |
| `terraform destroy` | Destroys infrastructure | Plan review, approval, state backup |
| `rm -rf` | Irreversible file deletion | Verify path before execution |
| `dd` | Can overwrite disks | Never use without verified target |
| `chmod -R 777` | Creates insecure permissions | Avoid; use least privilege |

## 19. RAG ingestion guidance

### 19.1 Chunking

- Split by `##` and `###` headings.
- Keep each chunk between approximately 500 and 1,500 tokens.
- Preserve the heading path in chunk metadata.
- Avoid splitting a command block from its explanation.
- Keep troubleshooting symptom, cause, command, resolution, and validation together.

### 19.2 Metadata

```json
{
  "document": "Multi_Cloud_Infrastructure_Engineering_RAG_Knowledge_Base",
  "version": "1.0",
  "cloud": "azure|aws|gcp|multi-cloud",
  "technology": "windows|linux|networking|security|migration",
  "section": "troubleshooting",
  "topic": "disk-full",
  "os": "windows|linux",
  "risk": "read-only|modifying|destructive",
  "review_date": "2026-11-17"
}
```

### 19.3 Embedding and retrieval

- Use a local embedding model compatible with Ollama or another supported local inference stack.
- Store chunks and metadata in ChromaDB.
- Retrieve top 5 to 10 chunks with similarity search.
- Include source heading and document version in generated answers.
- Prefer provider-specific chunks over generic answers when the user names Azure, AWS, or GCP.
- Flag destructive commands and require confirmation before execution.
- Refresh the corpus when cloud services, commands, or lifecycle dates change.

## 20. Assistant behavior rules

- Ask for cloud provider, environment, OS, and risk tolerance when unclear.
- Distinguish read-only diagnostics from modifying actions.
- Never execute destructive actions without explicit confirmation.
- Provide rollback and validation steps for production changes.
- Cite official documentation for provider-specific behavior.
- State assumptions and prerequisites.
- Avoid invented limits, pricing, or unsupported capabilities.
- Recommend least-privilege and change-controlled approaches.
