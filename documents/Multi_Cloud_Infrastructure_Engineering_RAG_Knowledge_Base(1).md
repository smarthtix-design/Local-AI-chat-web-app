

# Part 2 — Deep Azure Engineering Knowledge

## 21. Azure management groups and subscriptions

### 21.1 Purpose and design

Azure management groups provide a governance hierarchy above subscriptions. Policies, role assignments, and cost views can be inherited downward. A well-designed hierarchy prevents teams from bypassing security and cost controls while allowing controlled autonomy.

Recommended enterprise hierarchy:

```text
Tenant root
└── Platform
    ├── Management
    ├── Connectivity
    ├── Identity
    └── Security
└── Landing Zones
    ├── Corp
    ├── Online
    └── Sandbox
└── Decommissioned
```

### 21.2 Subscription design

| Subscription type | Contents | Access model |
|---|---|---|
| Management subscription | Log Analytics, automation, monitoring, backup vaults | Platform team only |
| Connectivity subscription | Hub VNets, firewalls, VPN/ExpressRoute gateways, DNS | Network team |
| Identity subscription | Domain controllers, identity proxy, Entra Connect | Identity team |
| Production workload subscription | Production applications and data | Application owners with least privilege |
| Non-production workload subscription | Dev, test, staging | Application owners with reduced guardrails |
| Sandbox subscription | Experimentation | Time-bound access and spend limits |

### 21.3 Azure Resource Manager

Azure Resource Manager (ARM) is the deployment and management layer. Resources are deployed through resource providers, and ARM templates, Bicep, Terraform, and the Azure CLI ultimately interact with the ARM control plane.

Key concepts:

- **Resource provider:** Service namespace that exposes resource types, such as `Microsoft.Compute`, `Microsoft.Network`, and `Microsoft.Storage`.
- **Resource ID:** Unique identifier, for example `/subscriptions/<subscription-id>/resourceGroups/<rg>/providers/Microsoft.Compute/virtualMachines/<vm>`.
- **Deployment:** Atomic or near-atomic deployment operation with rollback behavior depending on deployment mode and resource type.
- **Tags:** Metadata for ownership, cost allocation, environment, and automation.
- **Locks:** Prevent accidental deletion or modification; use carefully because they can block legitimate operations.

### 21.4 Azure Policy patterns

| Control | Example effect | Recommended scope |
|---|---|---|
| Allowed locations | Prevent deployment in unapproved regions | Management group |
| Required tags | Enforce `owner`, `environment`, `cost-center` | Management group or subscription |
| Allowed VM SKUs | Prevent expensive or unsupported VM families | Subscription or management group |
| Require encryption | Require CMK or platform-managed encryption where applicable | Data-heavy subscriptions |
| Deny public IP | Prevent direct Internet exposure for selected workloads | Production management group |
| Audit TLS version | Identify endpoints using weak TLS | Security management group |
| Deploy diagnostics | Deploy diagnostic settings to Log Analytics | Platform management group |

Policy should use **audit** first, then **deny** or **deployIfNotExists** after impact assessment. A deny policy can block deployments and break automation if exceptions are not planned.

### 21.5 Azure RBAC design

Use Microsoft Entra ID groups for human access. Assign Azure roles to groups, managed identities, or service principals—not directly to individual users where avoidable.

Example access model:

| Persona | Azure role | Scope |
|---|---|---|
| Cloud platform administrator | Owner or Contributor | Platform subscription only |
| Network engineer | Network Contributor | Connectivity subscription |
| Application developer | Contributor | Non-production resource group |
| Application operator | Reader plus targeted Contributor | Production resource group |
| Security analyst | Security Reader | Security scope |
| FinOps analyst | Cost Management Reader | Management group or subscription |
| Automation identity | Least-privilege custom or built-in role | Specific resource groups |

Avoid assigning `Owner` broadly. `Owner` includes the ability to assign RBAC roles, which can create privilege escalation paths.

### 21.6 Azure CLI operational examples

```bash
# Read-only: show current subscription
az account show

# Read-only: list resource groups in current subscription
az group list --query "[].{Name:name,Location:location}" -o table

# Read-only: list VMs with power state
az vm list --show-details \
  --query "[].{Name:name,ResourceGroup:resourceGroup,PowerState:powerState,Size:hardwareProfile.vmSize}" \
  -o table

# Read-only: show VM details
az vm show --resource-group <resource-group> --name <vm-name> --show-details

# Modifying: create a tagged resource group
az group create \
  --name <resource-group> \
  --location <region> \
  --tags environment=production owner=<team> cost-center=<cc>

# Modifying: add a tag to an existing resource group
az group update \
  --name <resource-group> \
  --set tags.environment=production

# Read-only: list network interfaces for a VM
az vm list-nics --resource-group <resource-group> --name <vm-name>

# Modifying: restart a VM
az vm restart --resource-group <resource-group> --name <vm-name>
```

**Safety:** `az vm deallocate` stops compute billing but preserves disks and networking. `az vm delete` deletes the VM resource; disks and public IPs may remain unless explicitly deleted. Always verify resource names before deletion.

## 22. Azure Virtual Machines

### 22.1 VM design decisions

| Decision | Guidance |
|---|---|
| Region | Select based on latency, data residency, service availability, and DR requirements |
| Availability zone | Use for zonal resilience when supported by the selected SKU and region |
| VM size family | Match workload profile: general purpose, compute optimized, memory optimized, storage optimized |
| OS disk | Use managed disk; separate OS and application/data disks where practical |
| Data disk | Size for IOPS and throughput, not only capacity |
| Networking | Use private IP; expose public IP only when required |
| Identity | Use managed identity instead of stored credentials where supported |
| Backup | Enable Azure Backup or approved backup solution |
| Monitoring | Install supported monitoring agent and configure diagnostics |
| Patching | Use Azure Update Manager, maintenance configurations, or approved patch tooling |

### 22.2 VM naming and tagging

A consistent naming convention improves automation, cost reporting, and incident response.

Example:

```text
<org>-<environment>-<workload>-<role>-<region>-<sequence>
```

Example VM name:

```text
contoso-prod-erp-app-weu-001
```

Required tags:

| Tag | Example |
|---|---|
| `owner` | `cloud-platform-team` |
| `environment` | `production`, `non-production` |
| `application` | `erp` |
| `cost-center` | `cc-1234` |
| `data-classification` | `internal`, `confidential`, `restricted` |
| `criticality` | `tier-1`, `tier-2`, `tier-3` |
| `backup-policy` | `daily-35d` |
| `dr-tier` | `rpo-15m-rto-4h` |

### 22.3 Windows VM build baseline

1. Deploy from an approved golden image or supported marketplace image.
2. Apply the latest approved OS patches.
3. Join the VM to the domain or apply the required workgroup baseline.
4. Configure time synchronization.
5. Install monitoring, security, backup, and configuration-management agents.
6. Configure firewall rules and management access.
7. Apply disk encryption where required.
8. Configure page file, storage layout, and application prerequisites.
9. Validate application service health.
10. Register the VM in CMDB and monitoring.
11. Create a pre-production backup or snapshot where appropriate.
12. Document build configuration and owner.

### 22.4 Linux VM build baseline

1. Deploy from an approved image.
2. Apply security updates.
3. Create an administrative user with SSH key authentication.
4. Disable direct root SSH where policy requires.
5. Configure NTP/chrony.
6. Install monitoring, security, backup, and configuration-management agents.
7. Configure firewall rules.
8. Configure disk encryption where required.
9. Validate service health.
10. Register the VM in CMDB and monitoring.
11. Document build configuration and owner.

### 22.5 Azure VM troubleshooting

| Symptom | Diagnostic area | Commands or checks |
|---|---|---|
| VM cannot be reached | VM state, NSG, NIC, IP, OS firewall | `az vm show`, `az network nic list-effective-nsg`, boot diagnostics |
| RDP fails | NSG, Bastion, public IP, NLA, credentials | Test port 3389, review NSG rules, check Windows event logs |
| SSH fails | NSG, SSH service, key permissions, OS firewall | `systemctl status sshd`, `ss -tulnp`, review `/var/log/auth.log` or `secure` |
| VM slow | CPU, memory, disk, network, application | Azure Monitor metrics, guest OS counters, `top`, `iostat` |
| Boot failure | OS corruption, disk issue, extension failure | Boot diagnostics, serial console, restore from backup |
| Extension failure | Agent status, permissions, network access | Review VM extensions and agent logs |

## 23. Azure networking deep dive

### 23.1 VNet and subnet planning

Use non-overlapping address spaces across on-premises, Azure, AWS, and GCP. Reserve address space for growth, gateways, private endpoints, and Kubernetes networking.

Example enterprise plan:

| Network | CIDR | Purpose |
|---|---|---|
| On-premises | `10.10.0.0/16` | Corporate data center |
| Azure hub | `10.20.0.0/16` | Shared Azure services |
| Azure spoke A | `10.21.0.0/16` | Application A |
| Azure spoke B | `10.22.0.0/16` | Application B |
| AWS VPC | `10.30.0.0/16` | AWS workloads |
| GCP VPC | `10.40.0.0/16` | GCP workloads |

Do not assume that all Azure services consume addresses in the same way. Some managed services inject subnets, reserve IPs, or require dedicated subnets. Validate service-specific requirements before finalizing the design.

### 23.2 Azure Firewall

Azure Firewall provides centralized network traffic inspection and policy enforcement.

Typical deployment:

- Deploy in a dedicated firewall subnet.
- Route spoke traffic to the firewall through user-defined routes.
- Use DNAT rules only when inbound publishing is required.
- Use application rules for FQDN-based outbound control.
- Use network rules for IP/port-based control.
- Send diagnostic logs to Log Analytics.
- Test rule changes in non-production where possible.

### 23.3 Private Endpoints and Private Link

Private Endpoints assign a private IP from a VNet to a supported PaaS service. Private Link is the underlying connectivity mechanism.

Design considerations:

- Use a dedicated subnet for private endpoints where appropriate.
- Configure private DNS zones so service names resolve to private IPs.
- Disable public network access for sensitive services where supported.
- Ensure DNS resolution works from hybrid clients.
- Validate that on-premises DNS can forward to Azure private DNS or use appropriate DNS architecture.

### 23.4 ExpressRoute and VPN

| Attribute | ExpressRoute | Site-to-Site VPN |
|---|---|---|
| Connectivity | Private dedicated or provider-based | Encrypted over Internet |
| Typical use | Predictable latency, high bandwidth, private connectivity | Lower-cost or backup connectivity |
| Encryption | Can use IPsec depending on design | IPsec |
| Failover | Often paired with VPN | Often used as backup path |
| Planning | Circuit, peering, routing, bandwidth | Gateway SKU, local network gateway, BGP |

### 23.5 Azure DNS design

Use Azure Private DNS Zones for internal Azure name resolution. For hybrid resolution:

- On-premises DNS forwards Azure-specific domains to Azure DNS resolver or DNS endpoints.
- Azure DNS forwards on-premises domains to on-premises DNS servers.
- Avoid split-brain DNS unless carefully designed.
- Document DNS zones, forwarders, and conditional forwarders.

## 24. Azure storage and data protection

### 24.1 Storage account design

| Requirement | Control |
|---|---|
| Confidential data | Private endpoint, encryption, restricted access |
| Backup data | Separate storage account, immutability where required |
| Logs | Lifecycle policy to move old data to lower-cost tiers |
| File shares | Azure Files with identity-based authentication where supported |
| Static website | CDN/front-door and access controls |

### 24.2 Azure Backup

Azure Backup supports VM backup, file share backup, blob backup, and other workload protection depending on configuration.

Backup design:

- Define backup policy by criticality.
- Use daily, weekly, monthly, and yearly retention only where required.
- Use cross-region restore or geo-redundant storage where DR requirements demand it.
- Test file-level, VM-level, and application-level restores.
- Monitor failed jobs and retention compliance.
- Protect backup vaults with RBAC and, where appropriate, immutability.

### 24.3 Azure Site Recovery

Azure Site Recovery supports replication and failover for supported workloads.

DR design:

- Identify protected VMs and dependencies.
- Define recovery plans with startup order.
- Test failover in isolated test failover mode.
- Validate DNS, IP addressing, certificates, and application integration.
- Document failback procedure.
- Monitor replication health and RPO.

## 25. Azure Monitor and Log Analytics

### 25.1 Monitoring architecture

Centralize logs in Log Analytics workspaces. Separate workloads by data ownership, retention, access, and cost requirements.

| Data type | Examples | Retention guidance |
|---|---|---|
| Platform metrics | CPU, memory, disk, network | Short operational retention |
| Diagnostic logs | NSG flow logs, firewall logs, PaaS logs | Security and compliance dependent |
| Application logs | Application telemetry, errors | Application-specific |
| Audit logs | Entra ID, Azure activity logs | Long retention for compliance |
| Security logs | Defender, Sentinel, identity logs | Incident-response dependent |

### 25.2 Alert design

| Alert | Threshold approach | Action |
|---|---|---|
| VM unavailable | Heartbeat missing or health signal | Page on-call |
| High CPU | Sustained threshold over time | Investigate and scale if needed |
| Disk full | Predictive and absolute thresholds | Clean or expand disk |
| Backup failure | Job failure | Investigate and rerun if safe |
| Certificate expiry | Days before expiry | Renew certificate |
| Replication lag | RPO threshold breach | Investigate replication path |
| Cost anomaly | Budget or anomaly detection | Notify owner |

Avoid alert fatigue. Alerts must be actionable, owned, and linked to a runbook.

# Part 3 — Deep AWS Engineering Knowledge

## 26. AWS Organizations and identity

### 26.1 Account strategy

Use account isolation as the primary security and blast-radius boundary.

| Account | Purpose |
|---|---|
| Management | Organization administration only |
| Audit / Log Archive | Centralized CloudTrail and security logs |
| Security Tooling | GuardDuty, Security Hub, Config, IAM Access Analyzer |
| Shared Services | DNS, monitoring, CI/CD, operational tooling |
| Network | Transit Gateway, Direct Connect, centralized egress |
| Workload Production | Production workloads |
| Workload Non-Production | Development, test, staging |
| Sandbox | Experimentation |

### 26.2 IAM Identity Center

IAM Identity Center provides centralized workforce access across AWS accounts.

Best practices:

- Use Identity Center groups mapped to permission sets.
- Use least-privilege permission sets.
- Require MFA.
- Use short-duration sessions.
- Avoid long-lived access keys for humans.
- Review access regularly.
- Use break-glass procedures for emergency access.

### 26.3 IAM roles and policies

Use roles for workloads and cross-account access. Prefer managed policies for common patterns and customer-managed policies for controlled custom permissions.

Example least-privilege policy concept:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::<bucket-name>/*"
      ]
    }
  ]
}
```

Avoid `Resource: "*"` unless the service requires it and the risk is accepted.

### 26.4 AWS CLI examples

```bash
# Read-only: current identity
aws sts get-caller-identity

# Read-only: list IAM roles
aws iam list-roles --query "Roles[].RoleName" --output text

# Read-only: list VPCs
aws ec2 describe-vpcs \
  --query "Vpcs[].{ID:VpcId,CIDR:CidrBlock,Name:Tags[?Key=='Name']|[0].Value}" \
  --output table

# Read-only: list subnets
aws ec2 describe-subnets \
  --query "Subnets[].{ID:SubnetId,CIDR:CidrBlock,AZ:AvailabilityZone}" \
  --output table

# Read-only: list security groups
aws ec2 describe-security-groups \
  --query "SecurityGroups[].{ID:GroupId,Name:GroupName}" \
  --output table

# Modifying: authorize an inbound SSH rule
aws ec2 authorize-security-group-ingress \
  --group-id <security-group-id> \
  --protocol tcp \
  --port 22 \
  --cidr <approved-cidr>
```

**Safety:** Security-group rule changes can expose services. Restrict source CIDRs and remove temporary rules after use.

## 27. Amazon EC2 and compute

### 27.1 EC2 design

| Decision | Guidance |
|---|---|
| Instance family | Match CPU, memory, storage, and network requirements |
| Placement group | Use when low latency or spread strategy is required |
| AMI | Use approved, patched, and version-controlled images |
| IAM instance profile | Grant least-privilege role |
| EBS volumes | Separate OS and data volumes; encrypt where required |
| Elastic IP | Avoid unless static public IP is required |
| User data | Use for repeatable bootstrap; avoid secrets in plaintext |
| Systems Manager | Use for patching, inventory, automation, and session access |

### 27.2 EC2 troubleshooting

| Symptom | Checks |
|---|---|
| Instance unreachable | Instance state, security group, route table, NACL, OS firewall, public IP |
| SSH fails | Security group port 22, key pair, OS SSH config, IAM/network path |
| Instance fails health checks | System status, instance status, boot logs, application logs |
| High CPU | CloudWatch metrics, process list, application logs |
| Disk full | EBS usage, log growth, inode usage, application data |
| EBS latency | IOPS, throughput, queue depth, volume type, instance limits |

### 27.3 Systems Manager

AWS Systems Manager provides operational management capabilities including Session Manager, Patch Manager, State Manager, Run Command, and inventory.

Use cases:

- Browser or CLI-based shell access without opening inbound SSH ports.
- Automated patching windows.
- Configuration compliance.
- Runbook automation.
- Inventory collection.
- Secure command execution with audit logging.

## 28. AWS networking deep dive

### 28.1 VPC design

Use separate VPCs for production and non-production where possible. Use private subnets for workloads and public subnets only for required Internet-facing resources.

Example:

| Subnet | CIDR | Purpose |
|---|---|---|
| Public A | `10.30.1.0/24` | Load balancers or NAT |
| Private app A | `10.30.10.0/24` | Application tier |
| Private app B | `10.30.11.0/24` | Application tier |
| Private data A | `10.30.20.0/24` | Database tier |
| Private data B | `10.30.21.0/24` | Database tier |

### 28.2 Transit Gateway

Transit Gateway simplifies VPC-to-VPC and hybrid connectivity.

Design points:

- Use separate route tables for production and non-production.
- Control route propagation deliberately.
- Use centralized egress through a firewall VPC where required.
- Avoid unnecessary transitive routing.
- Monitor Transit Gateway metrics and flow logs.

### 28.3 Direct Connect and VPN

Direct Connect provides dedicated private connectivity. Site-to-Site VPN provides encrypted connectivity over the Internet.

Common pattern:

- Direct Connect as primary.
- Site-to-Site VPN as backup.
- BGP for dynamic routing where supported.
- Separate routing domains for production and non-production.
- Test failover regularly.

## 29. AWS storage and backup

### 29.1 S3 design

| Control | Purpose |
|---|---|
| Block Public Access | Prevent accidental public exposure |
| Bucket policies | Enforce access rules |
| IAM policies | Control identity access |
| Encryption | Protect data at rest |
| Versioning | Protect against accidental overwrite/delete |
| Object Lock | Immutability for compliance or ransomware resilience |
| Lifecycle policy | Move data between storage classes |
| Replication | Cross-region or cross-account copy |

### 29.2 EBS, EFS, and FSx

| Service | Use case | Backup approach |
|---|---|---|
| EBS | Block storage for EC2 | Snapshots and AWS Backup |
| EFS | Shared POSIX file system | AWS Backup |
| FSx for Windows File Server | Windows SMB workloads | AWS Backup |
| FSx for NetApp ONTAP | Enterprise NAS and advanced features | Service-specific backup |
| S3 | Object storage | Versioning, replication, backup |

### 29.3 AWS Backup

Use backup plans to standardize retention, copy, and vault configuration.

Example policy tiers:

| Tier | Daily backup | Retention | Cross-region copy |
|---|---:|---:|---|
| Tier 1 | Yes | 35 days | Yes |
| Tier 2 | Yes | 14 days | Optional |
| Tier 3 | Weekly | 7 days | No |

Validate restore procedures for each tier.

## 30. AWS observability and security

### 30.1 CloudWatch and CloudTrail

CloudWatch collects metrics, logs, alarms, and events. CloudTrail records API activity.

Recommended controls:

- Enable organization-level CloudTrail where supported.
- Store logs in a dedicated log-archive account.
- Use S3 object lock or equivalent immutability where compliance requires.
- Create CloudWatch alarms for critical metrics.
- Use CloudWatch Logs Insights for operational investigations.
- Send security findings to Security Hub.

### 30.2 AWS security services

| Service | Purpose |
|---|---|
| GuardDuty | Threat detection |
| Security Hub | Security posture aggregation |
| Config | Resource configuration compliance |
| IAM Access Analyzer | Identify unintended external access |
| Detective | Investigation and visualization |
| KMS | Key management |
| Secrets Manager | Secrets management |
| WAF | Web application firewall |

# Part 4 — Deep GCP Engineering Knowledge

## 31. GCP organization and IAM

### 31.1 Resource hierarchy

Use folders to group projects by environment, business unit, or application. Use projects as deployment and billing boundaries.

Example:

```text
Organization
└── Folder: Platform
    ├── Project: Networking
    ├── Project: Security
    └── Project: Logging
└── Folder: Applications
    ├── Project: App A Production
    ├── Project: App A Non-Production
    └── Project: App B Production
```

### 31.2 IAM design

GCP IAM uses roles bound to identities at organization, folder, project, or resource level.

| Persona | Role pattern | Scope |
|---|---|---|
| Platform administrator | Organization-level limited roles | Organization or folder |
| Network engineer | Network roles | Host project |
| Application developer | Project-level roles | Non-production project |
| Security analyst | Security roles | Security project |
| Billing analyst | Billing roles | Billing account or organization |
| Service account | Least-privilege role | Specific project or resource |

Avoid primitive roles such as `Owner`, `Editor`, and `Viewer` for broad production use. Prefer predefined or custom roles with least privilege.

### 31.3 gcloud IAM examples

```bash
# Read-only: current authenticated account
gcloud auth list

# Read-only: list IAM policy bindings for a project
gcloud projects get-iam-policy <project-id>

# Read-only: list service accounts
gcloud iam service-accounts list --project <project-id>

# Modifying: grant a role to a user
gcloud projects add-iam-policy-binding <project-id> \
  --member="user:<email>" \
  --role="roles/<role-name>"

# Modifying: remove a role binding
gcloud projects remove-iam-policy-binding <project-id> \
  --member="user:<email>" \
  --role="roles/<role-name>"
```

**Safety:** IAM changes affect access immediately or after propagation. Validate the exact member and role before applying.

## 32. Compute Engine and storage

### 32.1 Compute Engine design

| Decision | Guidance |
|---|---|
| Machine family | Match CPU, memory, and workload characteristics |
| Region and zone | Use multiple zones for availability |
| Image | Use approved, hardened, and updated images |
| Service account | Use least-privilege service account |
| Disk | Use Persistent Disk or Hyperdisk according to performance needs |
| Shielded VM | Use where supported and required |
| OS Login | Use where identity-based SSH is appropriate |
| Backup | Use Backup and DR Service or approved snapshots |

### 32.2 Persistent Disk and Cloud Storage

| Service | Use case | Protection |
|---|---|---|
| Persistent Disk | VM block storage | Snapshots |
| Hyperdisk | Higher-performance block storage | Snapshots |
| Cloud Storage | Object storage | Versioning, retention, replication |
| Filestore | Managed NFS | Backup and DR Service |
| Cloud SQL | Managed relational database | Automated backups and PITR where supported |

### 32.3 gcloud storage examples

```bash
# Read-only: list buckets
gcloud storage buckets list

# Read-only: list objects in a bucket
gcloud storage ls gs://<bucket-name>

# Modifying: create a bucket
gcloud storage buckets create gs://<bucket-name> --location=<region>

# Modifying: upload a file
gcloud storage cp <local-file> gs://<bucket-name>/<object-path>

# Modifying: delete an object
gcloud storage rm gs://<bucket-name>/<object-path>
```

**Safety:** `gcloud storage rm` deletes objects. Confirm bucket and object path before execution.

## 33. GCP networking deep dive

### 33.1 VPC design

GCP VPCs can be global or regional depending on configuration. Subnets are regional.

| Component | Purpose |
|---|---|
| VPC | Network boundary |
| Subnet | Regional IP range |
| Firewall rule | VPC-level traffic rule |
| Cloud Router | Dynamic routing for VPN/Interconnect |
| Cloud NAT | Outbound Internet access |
| Cloud Interconnect | Dedicated private connectivity |
| Private Service Connect | Private service access |
| Cloud DNS | Managed DNS |

### 33.2 Firewall rule design

Use least-privilege ingress and egress rules.

Example:

| Direction | Source | Target | Port | Action |
|---|---|---|---|---|
| Ingress | Approved management CIDR | Tag `ssh` | 22 | Allow |
| Ingress | Internal VPC | Tag `app` | 8080 | Allow |
| Ingress | Internet | Tag `web` | 443 | Allow |
| Egress | Tag `app` | Approved API ranges | 443 | Allow |
| Egress | All | Internet | All | Deny unless required |

### 33.3 Hybrid connectivity

Cloud VPN and Cloud Interconnect connect GCP to on-premises networks. Cloud Router exchanges routes dynamically where BGP is used.

Validation checklist:

- [ ] Tunnel or Interconnect attachment is up
- [ ] BGP sessions established where applicable
- [ ] Routes are advertised and learned correctly
- [ ] Firewall rules permit required traffic
- [ ] DNS resolution works across environments
- [ ] Failover path tested
- [ ] Monitoring and logging operational

## 34. GKE and containers

### 34.1 GKE architecture

| Component | Responsibility |
|---|---|
| GKE control plane | Managed by Google |
| Node pools | Customer-managed configuration and workloads |
| Workloads | Customer-managed |
| Networking | Shared responsibility |
| Identity | Customer-managed IAM and workload identity |
| Security policy | Customer-managed policy and enforcement |
| Logging | Shared responsibility |

### 34.2 GKE operational baseline

- Use private clusters for production.
- Use separate node pools for system and application workloads.
- Use Workload Identity Federation for Google Cloud access.
- Enable audit logging.
- Use Network Policy for segmentation.
- Use resource requests and limits.
- Use readiness and liveness probes.
- Use rolling updates and rollback strategy.
- Use PodDisruptionBudgets for critical workloads.
- Use horizontal and vertical scaling where appropriate.

## 35. GCP security and governance

### 35.1 Organization policies

Organization policies provide guardrails across the resource hierarchy.

Examples:

- Restrict resource locations.
- Restrict external IP access.
- Restrict service account key creation.
- Require Shielded VM.
- Restrict public bucket access.
- Enforce domain-restricted sharing.

### 35.2 Security Command Center

Security Command Center provides security posture management, vulnerability findings, and threat detection depending on configuration and edition.

Operational practices:

- Assign findings owners.
- Prioritize by severity and exploitability.
- Integrate findings with incident management.
- Review recurring findings.
- Track remediation SLAs.
- Validate fixes through rescans or controls.

# Part 5 — Advanced Windows Server Operations

## 36. Active Directory operations

### 36.1 Domain controller placement

Place domain controllers close to users and workloads where possible. In cloud environments, deploy at least two domain controllers in separate availability zones or regions where supported.

Design considerations:

- Use at least two domain controllers per critical domain.
- Avoid single points of failure.
- Protect DNS availability.
- Secure replication traffic.
- Monitor replication, authentication, DNS, disk, and time synchronization.
- Back up system state and AD database where supported.
- Use read-only domain controllers where appropriate for branch or restricted environments.

### 36.2 AD replication troubleshooting

```powershell
# Read-only: replication summary
repadmin /replsummary

# Read-only: show replication partners
repadmin /showrepl *

# Read-only: force knowledge consistency checker
repadmin /kcc *

# Read-only: check replication metadata
repadmin /showmeta "<distinguished-name>"

# Read-only: check for lingering objects
repadmin /removelingeringobjects <target-dc> <source-dc-guid> <naming-context> /advisory_mode
```

Common causes:

- Network or firewall blocking required ports.
- DNS resolution failure.
- Time skew.
- USN rollback.
- Tombstone lifetime issues.
- Lingering objects.
- Disk or database corruption.

Required ports commonly include Kerberos, RPC, LDAP, LDAPS, SMB, DNS, and Kerberos password change traffic. Validate current Microsoft documentation and environment-specific requirements before opening firewall rules.

### 36.3 Group Policy troubleshooting

```powershell
# Read-only: list applied GPOs
gpresult /r

# Read-only: generate HTML report
gpresult /h C:\Temp\gpo-report.html

# Read-only: force policy refresh
gpupdate /force

# Read-only: check event logs
Get-WinEvent -LogName 'Microsoft-Windows-GroupPolicy/Operational' -MaxEvents 50
```

Troubleshooting sequence:

1. Confirm the computer and user are in the expected OU.
2. Confirm GPO link scope and security filtering.
3. Confirm network access to domain controllers.
4. Confirm DNS resolution.
5. Review Group Policy operational logs.
6. Test with Group Policy Modeling.
7. Review WMI filters and loopback processing.

## 37. Windows performance and reliability

### 37.1 Performance counters

| Counter | Meaning | Concern threshold |
|---|---|---|
| Processor time | CPU utilization | Sustained high utilization |
| Available memory | Available physical memory | Persistent low memory |
| Disk queue length | Pending disk requests | Sustained high queue |
| Disk latency | Time per I/O operation | High latency |
| Network utilization | Network throughput | Capacity or contention |
| TCP retransmissions | Network reliability | Elevated retransmissions |

### 37.2 Event log investigation

```powershell
# Read-only: critical and error events
Get-WinEvent -FilterHashtable @{
  LogName='System'
  Level=1,2
  StartTime=(Get-Date).AddDays(-1)
} | Select-Object TimeCreated, Id, ProviderName, Message

# Read-only: application errors
Get-WinEvent -FilterHashtable @{
  LogName='Application'
  Level=1,2
  StartTime=(Get-Date).AddDays(-1)
} | Select-Object TimeCreated, Id, ProviderName, Message
```

### 37.3 Certificate troubleshooting

```powershell
# Read-only: list certificates in Local Machine personal store
Get-ChildItem Cert:\LocalMachine\My

# Read-only: find certificates expiring soon
Get-ChildItem Cert:\LocalMachine\My |
  Where-Object { $_.NotAfter -lt (Get-Date).AddDays(30) } |
  Select-Object Subject, NotAfter, Thumbprint

# Read-only: test TLS endpoint
Test-NetConnection -ComputerName <hostname> -Port 443
```

## 38. Windows backup and recovery

### 38.1 Backup types

| Type | Description | Use case |
|---|---|---|
| Full | Complete data copy | Baseline or critical recovery |
| Incremental | Changes since last backup | Efficient frequent backups |
| Differential | Changes since last full backup | Simpler restore chain |
| System state | OS configuration, registry, AD data where applicable | Domain controller recovery |
| Bare-metal recovery | Full OS and system recovery | Server rebuild |
| Application-consistent | Application quiesced for backup | Databases and transactional systems |
| Crash-consistent | Point-in-time disk state | VMs where app consistency is unavailable |

### 38.2 Recovery validation

- [ ] Backup job completed successfully
- [ ] Backup is stored in expected location
- [ ] Recovery point meets RPO
- [ ] Restore tested in isolated environment
- [ ] Application functionality verified
- [ ] Data integrity verified
- [ ] Security controls restored
- [ ] Monitoring restored
- [ ] Documentation updated

# Part 6 — Advanced Linux Operations

## 39. Linux boot, services, and recovery

### 39.1 systemd service management

```bash
# Read-only: service status
systemctl status <service-name>

# Read-only: list failed services
systemctl --failed

# Modifying: start service
sudo systemctl start <service-name>

# Modifying: stop service
sudo systemctl stop <service-name>

# Modifying: enable service at boot
sudo systemctl enable <service-name>

# Modifying: disable service at boot
sudo systemctl disable <service-name>

# Read-only: service logs
journalctl -u <service-name> -n 100 --no-pager
```

### 39.2 Boot troubleshooting

```bash
# Read-only: boot logs
journalctl -b -p err

# Read-only: previous boot logs
journalctl -b -1 -p err

# Read-only: kernel messages
sudo dmesg -T | tail -100

# Read-only: filesystem check status
systemctl status systemd-fsck-root
```

Common boot issues:

- Incorrect fstab entry
- Missing or corrupted filesystem
- Disk device name change
- Failed mount
- Kernel or driver issue
- Insufficient disk space
- Failed service dependency

### 39.3 Emergency recovery

1. Access console or rescue mode.
2. Identify boot failure from logs.
3. Mount root filesystem read-only where appropriate.
4. Correct `/etc/fstab`, network, or service configuration.
5. Validate filesystem integrity.
6. Reboot and validate.
7. Document root cause and preventive action.

## 40. Linux storage operations

### 40.1 Disk and LVM workflow

```bash
# Read-only: identify new disk
lsblk
sudo fdisk -l

# Modifying: create a physical volume
sudo pvcreate /dev/<device>

# Modifying: create a volume group
sudo vgcreate <vg-name> /dev/<device>

# Modifying: create a logical volume
sudo lvcreate -L <size> -n <lv-name> <vg-name>

# Modifying: create ext4 filesystem
sudo mkfs.ext4 /dev/<vg-name>/<lv-name>

# Modifying: create XFS filesystem
sudo mkfs.xfs /dev/<vg-name>/<lv-name>

# Modifying: mount filesystem
sudo mkdir -p /<mount-point>
sudo mount /dev/<vg-name>/<lv-name> /<mount-point>
```

### 40.2 Disk-full response

```bash
# Read-only: identify filesystem usage
df -h

# Read-only: identify inode usage
df -i

# Read-only: find large files
sudo find / -xdev -type f -size +100M -exec ls -lh {} \;

# Read-only: identify large directories
sudo du -h --max-depth=2 / 2>/dev/null | sort -h | tail -30

# Read-only: identify deleted but open files
sudo lsof +L1
```

Do not delete files without confirming ownership, application impact, and backup status.

## 41. Linux security operations

### 41.1 Hardening checklist

- [ ] Remove unused packages and services
- [ ] Disable direct root SSH where policy allows
- [ ] Use key-based SSH authentication
- [ ] Restrict sudo to required commands
- [ ] Enable automatic security updates where appropriate
- [ ] Configure host firewall
- [ ] Enable audit logging
- [ ] Configure centralized logging
- [ ] Enforce time synchronization
- [ ] Apply CIS or organization baseline
- [ ] Scan for vulnerabilities
- [ ] Monitor authentication failures

### 41.2 Audit and authentication

```bash
# Read-only: recent SSH logins
sudo journalctl -u ssh -n 100

# Read-only: authentication failures
sudo grep -i "failed password" /var/log/auth.log | tail -20

# Read-only: sudo usage
sudo grep sudo /var/log/auth.log | tail -20

# Read-only: audit rules
sudo auditctl -l

# Read-only: audit logs
sudo ausearch -k <key-name> -ts recent
```

# Part 7 — Enterprise Migration Playbooks

## 42. Migration factory model

A migration factory standardizes repeated migration work.

| Role | Responsibility |
|---|---|
| Migration lead | Overall delivery and governance |
| Cloud architect | Target architecture and design |
| Network engineer | Connectivity, DNS, routing, firewall |
| Windows engineer | Windows server migration |
| Linux engineer | Linux server migration |
| Database engineer | Database migration and validation |
| Application owner | Functional validation |
| Security engineer | Security review and controls |
| Operations engineer | Monitoring, backup, runbooks |
| Project manager | Schedule, risks, communication |

## 43. Discovery and assessment

### 43.1 Technical discovery

Collect:

- Server inventory
- CPU, memory, disk, and network utilization
- Operating system and version
- Installed software
- Running services
- Scheduled jobs
- Certificates
- Firewall rules
- DNS dependencies
- Database dependencies
- Application dependencies
- Integration endpoints
- Backup configuration
- Licensing constraints

### 43.2 Dependency mapping

Use a dependency matrix:

| Source | Destination | Protocol | Port | Direction | Criticality |
|---|---|---|---:|---|---|
| App server | Database | TCP | 1433 | Outbound | High |
| App server | LDAP | TCP | 636 | Outbound | High |
| Web server | App server | TCP | 8080 | Outbound | High |
| Monitoring | All servers | TCP | 443 | Inbound | Medium |

### 43.3 Migration readiness score

| Area | Ready | Conditional | Not ready |
|---|---|---|---|
| Application compatibility | Validated | Needs testing | Unknown |
| OS support | Supported | Extended support | End of support |
| Dependencies | Mapped | Partially mapped | Unknown |
| Backup | Tested | Configured | Missing |
| Security | Approved | Exceptions required | Not assessed |
| Network | Ready | Changes required | Not designed |
| Rollback | Tested | Documented | Missing |

## 44. Migration wave planning

| Wave | Content | Entry criteria | Exit criteria |
|---|---|---|---|
| Wave 0 | Pilot | Low-risk servers, test applications | Process validated |
| Wave 1 | Non-production | Dependencies mapped, network ready | Test migration complete |
| Wave 2 | Low-risk production | Rollback tested | Production validated |
| Wave 3 | Medium-risk production | Hypercare ready | Production validated |
| Wave 4 | Critical production | Full rollback and DR validation | Production validated |

## 45. Cutover and rollback

### 45.1 Cutover checklist

- [ ] Change approved
- [ ] Maintenance window confirmed
- [ ] Stakeholders notified
- [ ] Backups completed and verified
- [ ] Source and target synchronized
- [ ] DNS changes prepared
- [ ] Firewall rules prepared
- [ ] Monitoring configured
- [ ] Validation scripts ready
- [ ] Rollback procedure ready
- [ ] Hypercare team available

### 45.2 Rollback checklist

- [ ] Rollback owner identified
- [ ] Rollback decision criteria defined
- [ ] Source environment retained
- [ ] Data rollback path defined
- [ ] DNS rollback prepared
- [ ] Application rollback tested
- [ ] Communication plan ready
- [ ] Rollback window defined

## 46. Database migration

### 46.1 Migration approaches

| Approach | Description | Downtime |
|---|---|---|
| Backup and restore | Restore backup to target | Depends on restore time |
| Log shipping / replication | Continuous replication | Low |
| Native replication | Database-native replication | Low |
| CDC-based migration | Change data capture | Low |
| Export and import | Logical export/import | Depends on data size |

### 46.2 Database validation

- [ ] Schema objects migrated
- [ ] Row counts validated
- [ ] Data checksums validated where applicable
- [ ] Stored procedures validated
- [ ] Jobs and schedules migrated
- [ ] Users and permissions migrated
- [ ] Connection strings updated
- [ ] Performance validated
- [ ] Backup configured
- [ ] Monitoring configured
- [ ] Rollback tested

# Part 8 — Enterprise Troubleshooting Library

## 47. Troubleshooting method

Use a repeatable method:

1. Define the symptom.
2. Identify impacted users and scope.
3. Check recent changes.
4. Validate infrastructure layer.
5. Validate network layer.
6. Validate identity layer.
7. Validate application layer.
8. Validate data layer.
9. Identify root cause.
10. Apply resolution.
11. Validate recovery.
12. Document and prevent recurrence.

## 48. Troubleshooting matrix

| Issue | Symptoms | First checks | Common causes | Resolution |
|---|---|---|---|---|
| VM unavailable | No access, monitoring offline | Cloud state, NSG/SG, boot logs | Stopped VM, firewall, OS failure | Start/repair/restore |
| High CPU | Slow response | Process list, metrics, logs | Runaway process, insufficient capacity | Identify and remediate |
| High memory | OOM, swapping | Memory usage, process list | Memory leak, undersizing | Restart or resize |
| Disk full | Application errors | `df -h`, logs, temp files | Log growth, backups, application data | Clean or expand |
| Disk latency | Slow application | IOPS, queue depth, latency | Insufficient performance, contention | Resize or optimize |
| Network failure | Timeout | Ping, route, firewall, DNS | ACL, route, firewall | Correct configuration |
| DNS failure | Name resolution errors | `dig`, `nslookup`, DNS logs | Wrong DNS, missing record | Correct DNS |
| Domain join failure | Authentication errors | DNS, time, credentials, network | DNS, time skew, permissions | Correct root cause |
| AD replication failure | Inconsistent data | `repadmin`, event logs | Network, DNS, time | Repair replication |
| Backup failure | Failed job | Agent, credentials, storage, network | Permission, connectivity, capacity | Fix and rerun |
| Certificate expiry | TLS errors | Certificate expiry, endpoint test | Expired certificate | Renew and deploy |
| Database failure | Connection errors | Service, port, credentials, network | Service down, firewall, credentials | Restore service |

## 49. Application service failure

### 49.1 Windows service troubleshooting

```powershell
# Read-only: service status
Get-Service -Name <service-name>

# Read-only: service dependencies
Get-Service -Name <service-name> -DependentServices

# Read-only: recent application events
Get-WinEvent -LogName Application -MaxEvents 100

# Modifying: restart service
Restart-Service -Name <service-name>
```

### 49.2 Linux service troubleshooting

```bash
# Read-only: service status
systemctl status <service-name>

# Read-only: service logs
journalctl -u <service-name> -n 200

# Read-only: listening port
sudo ss -tulnp | grep <port>

# Modifying: restart service
sudo systemctl restart <service-name>
```

# Part 9 — Automation Standards

## 50. Scripting standards

### 50.1 PowerShell standard

```powershell
#Requires -Version 5.1
<#
.SYNOPSIS
    Example operational script.
.DESCRIPTION
    Performs a controlled operational task with logging and error handling.
.EXAMPLE
    .\Example-Script.ps1 -ComputerName "server01"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$ComputerName
)

try {
    Write-Output "Starting operation on $ComputerName"
    # Operational logic here
}
catch {
    Write-Error "Operation failed: $($_.Exception.Message)"
    throw
}
finally {
    Write-Output "Operation completed"
}
```

### 50.2 Bash standard

```bash
#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="/var/log/example-script.log"

log() {
  printf '%s %s\n' "$(date --iso-8601=seconds)" "$*" | tee -a "$LOG_FILE"
}

log "Starting operation"

# Operational logic here

log "Operation completed"
```

### 50.3 Python standard

```python
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

def main():
    logging.info("Starting operation")
    # Operational logic here
    logging.info("Operation completed")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.error("Operation failed: %s", exc)
        sys.exit(1)
```

## 51. CI/CD for infrastructure

### 51.1 Pipeline stages

1. Lint
2. Validate
3. Plan
4. Security scan
5. Policy check
6. Manual approval
7. Apply
8. Post-deployment validation
9. Documentation update

### 51.2 Git standards

- Use feature branches.
- Require peer review.
- Protect main branch.
- Use conventional commit messages where possible.
- Store secrets outside source control.
- Use pipeline service connections with least privilege.
- Tag releases.
- Maintain rollback artifacts.

# Part 10 — FinOps Deep Dive

## 52. Cost allocation model

| Tag | Example | Required |
|---|---|---|
| `application` | `erp` | Yes |
| `environment` | `production` | Yes |
| `owner` | `finance-app-team` | Yes |
| `cost-center` | `cc-1234` | Yes |
| `business-unit` | `finance` | Yes |
| `criticality` | `tier-1` | Yes |
| `data-classification` | `confidential` | Yes |
| `created-by` | `terraform` | Recommended |

## 53. Cost optimization actions

| Action | Expected benefit | Risk |
|---|---|---|
| Rightsizing | Reduce overprovisioned compute | Performance impact if incorrect |
| Scheduled shutdown | Reduce non-production spend | Availability impact if misconfigured |
| Reserved capacity | Lower predictable compute cost | Commitment risk |
| Savings plans | Flexible commitment discounts | Commitment risk |
| Storage tiering | Reduce storage cost | Retrieval cost and access latency |
| Delete unattached disks | Remove waste | Data loss if wrong resource |
| Remove unused public IPs | Reduce networking cost | Connectivity impact |
| Optimize log retention | Reduce observability cost | Compliance or investigation impact |

## 54. FinOps operating cadence

| Frequency | Activity |
|---|---|
| Daily | Monitor anomalies and failed jobs |
| Weekly | Review budgets and top cost drivers |
| Monthly | Cost allocation and rightsizing review |
| Quarterly | Commitment strategy and architecture review |
| Annually | FinOps policy and tagging review |

# Part 11 — Enterprise Scenario Library

## 55. Scenario: Multi-region DR

### Business requirement

A Tier 1 application must tolerate a regional outage with RPO of 15 minutes and RTO of 4 hours.

### Technical requirements

- Replicate data to secondary region.
- Maintain application deployment capability in secondary region.
- Automate DNS or traffic-manager failover.
- Test failover quarterly.
- Maintain rollback capability.

### Architecture

```text
Primary region
├── Application tier
├── Database primary
└── Monitoring

Secondary region
├── Application tier
├── Database secondary
└── Monitoring

Global DNS / traffic manager
└── Health-based failover
```

### Implementation steps

1. Define RPO and RTO.
2. Select replication method.
3. Deploy secondary infrastructure.
4. Configure replication.
5. Configure DNS failover.
6. Configure monitoring.
7. Test failover.
8. Document failback.
9. Operate and review.

## 56. Scenario: Standardized landing zone

### Business requirement

Multiple application teams need secure, governed cloud environments.

### Architecture

- Central platform subscription/account/project for shared services.
- Workload subscriptions/accounts/projects per team.
- Hub-and-spoke networking.
- Centralized logging.
- Policy-as-code guardrails.
- Standardized tagging.
- Backup baseline.
- Cost allocation.

### Implementation steps

1. Define governance model.
2. Create management hierarchy.
3. Deploy connectivity.
4. Deploy security and logging.
5. Define policies.
6. Create workload landing zones.
7. Onboard teams.
8. Validate controls.
9. Operate and improve.

# Part 12 — RAG Implementation Guide

## 57. ChromaDB ingestion

### 57.1 Recommended chunking

- Split at `#`, `##`, and `###` headings.
- Keep sections between 500 and 1,500 tokens.
- Preserve parent heading path.
- Keep commands with explanations.
- Keep troubleshooting symptom, cause, command, resolution, and validation together.
- Avoid splitting tables across chunks.

### 57.2 Metadata schema

```json
{
  "source": "Multi_Cloud_Infrastructure_Engineering_RAG_Knowledge_Base",
  "version": "1.0",
  "section": "Azure Networking",
  "topic": "Private Endpoints",
  "cloud": "azure",
  "technology": "networking",
  "os": "none",
  "risk": "read-only",
  "review_date": "2026-11-17"
}
```

### 57.3 Retrieval strategy

- Use semantic search with metadata filtering.
- Retrieve 5 to 10 chunks.
- Re-rank results where supported.
- Include source heading in answers.
- Prefer provider-specific chunks.
- Flag destructive commands.
- Require confirmation for production changes.
- Refresh corpus on service and lifecycle changes.

## 58. Assistant response standards

When answering infrastructure questions, the assistant should:

- Identify cloud provider and environment.
- State assumptions.
- Separate read-only diagnostics from modifying actions.
- Provide exact commands with placeholders clearly marked.
- Explain expected output.
- Include validation steps.
- Include rollback and safety considerations.
- Avoid invented limits or pricing.
- Recommend least privilege and change control.
- Cite official documentation where appropriate.


# Part 13 — Detailed Command Reference

## 59. Azure CLI reference

| Command | Purpose | Risk | Example | Validation |
|---|---|---|---|---|
| `az account list` | List accessible subscriptions | Read-only | `az account list -o table` | Subscription names and IDs returned |
| `az account set` | Set active subscription | Modifying session context | `az account set --subscription <subscription-id>` | `az account show` reflects selection |
| `az group list` | List resource groups | Read-only | `az group list -o table` | Resource groups listed |
| `az group create` | Create resource group | Modifying | `az group create -n <rg> -l <region>` | Resource group created |
| `az vm list` | List virtual machines | Read-only | `az vm list -o table` | VM inventory returned |
| `az vm show` | Show VM details | Read-only | `az vm show -g <rg> -n <vm> -d` | VM configuration returned |
| `az vm start` | Start VM | Modifying | `az vm start -g <rg> -n <vm>` | VM power state becomes running |
| `az vm deallocate` | Deallocate VM | Modifying | `az vm deallocate -g <rg> -n <vm>` | VM stopped and deallocated |
| `az vm delete` | Delete VM | Destructive | `az vm delete -g <rg> -n <vm> --yes` | VM removed |
| `az network vnet list` | List VNets | Read-only | `az network vnet list -o table` | VNets listed |
| `az network nsg rule list` | List NSG rules | Read-only | `az network nsg rule list -g <rg> --nsg-name <nsg>` | Rules listed |
| `az monitor metrics list` | Query metrics | Read-only | `az monitor metrics list --resource <resource-id> --metric "Percentage CPU"` | Metric values returned |

### 59.1 Azure PowerShell reference

| Command | Purpose | Risk | Example |
|---|---|---|---|
| `Get-AzSubscription` | List subscriptions | Read-only | `Get-AzSubscription` |
| `Set-AzContext` | Set active subscription | Modifying session | `Set-AzContext -Subscription <subscription-id>` |
| `Get-AzResourceGroup` | List resource groups | Read-only | `Get-AzResourceGroup` |
| `Get-AzVM` | List VMs | Read-only | `Get-AzVM` |
| `Start-AzVM` | Start VM | Modifying | `Start-AzVM -ResourceGroupName <rg> -Name <vm>` |
| `Stop-AzVM` | Stop/deallocate VM | Modifying | `Stop-AzVM -ResourceGroupName <rg> -Name <vm>` |
| `Remove-AzVM` | Delete VM | Destructive | `Remove-AzVM -ResourceGroupName <rg> -Name <vm>` |
| `Get-AzNetworkSecurityGroup` | Get NSG | Read-only | `Get-AzNetworkSecurityGroup -Name <nsg> -ResourceGroupName <rg>` |

## 60. AWS CLI reference

| Command | Purpose | Risk | Example | Validation |
|---|---|---|---|---|
| `aws sts get-caller-identity` | Identify current identity | Read-only | `aws sts get-caller-identity` | Account, ARN, user ID returned |
| `aws ec2 describe-instances` | Describe EC2 instances | Read-only | `aws ec2 describe-instances` | Instance details returned |
| `aws ec2 start-instances` | Start instance | Modifying | `aws ec2 start-instances --instance-ids <id>` | Instance state changes |
| `aws ec2 stop-instances` | Stop instance | Modifying | `aws ec2 stop-instances --instance-ids <id>` | Instance state changes |
| `aws ec2 terminate-instances` | Terminate instance | Destructive | `aws ec2 terminate-instances --instance-ids <id>` | Instance terminated |
| `aws ec2 describe-security-groups` | List security groups | Read-only | `aws ec2 describe-security-groups` | Security groups listed |
| `aws s3 ls` | List buckets | Read-only | `aws s3 ls` | Buckets listed |
| `aws s3 cp` | Copy object | Modifying | `aws s3 cp <file> s3://<bucket>/<key>` | Object copied |
| `aws s3 rm` | Delete object | Destructive | `aws s3 rm s3://<bucket>/<key>` | Object deleted |
| `aws cloudwatch describe-alarms` | List alarms | Read-only | `aws cloudwatch describe-alarms` | Alarms listed |
| `aws logs tail` | Tail log group | Read-only | `aws logs tail <log-group> --follow` | Log events streamed |

## 61. Google Cloud CLI reference

| Command | Purpose | Risk | Example | Validation |
|---|---|---|---|---|
| `gcloud auth list` | List authenticated accounts | Read-only | `gcloud auth list` | Accounts listed |
| `gcloud config set project` | Set active project | Modifying session | `gcloud config set project <project-id>` | Configuration updated |
| `gcloud projects list` | List projects | Read-only | `gcloud projects list` | Projects listed |
| `gcloud compute instances list` | List VMs | Read-only | `gcloud compute instances list` | Instances listed |
| `gcloud compute instances start` | Start instance | Modifying | `gcloud compute instances start <name> --zone <zone>` | Instance running |
| `gcloud compute instances stop` | Stop instance | Modifying | `gcloud compute instances stop <name> --zone <zone>` | Instance terminated/stopped |
| `gcloud compute instances delete` | Delete instance | Destructive | `gcloud compute instances delete <name> --zone <zone>` | Instance deleted |
| `gcloud compute networks list` | List VPCs | Read-only | `gcloud compute networks list` | Networks listed |
| `gcloud compute firewall-rules list` | List firewall rules | Read-only | `gcloud compute firewall-rules list` | Rules listed |
| `gcloud logging read` | Read logs | Read-only | `gcloud logging read 'resource.type="gce_instance"' --limit 50` | Log entries returned |

# Part 14 — Kubernetes Operations

## 62. Kubernetes fundamentals

Kubernetes is a container orchestration platform. It manages workloads through declarative objects such as Pods, Deployments, Services, ConfigMaps, Secrets, PersistentVolumeClaims, Namespaces, and Ingress resources.

| Object | Purpose |
|---|---|
| Pod | Smallest deployable unit |
| Deployment | Declarative workload management |
| ReplicaSet | Maintains desired Pod count |
| Service | Stable network endpoint |
| Ingress | HTTP/HTTPS routing |
| ConfigMap | Non-sensitive configuration |
| Secret | Sensitive configuration |
| PersistentVolumeClaim | Storage request |
| Namespace | Logical isolation |
| NetworkPolicy | Pod traffic control |

## 63. Kubernetes commands

```bash
# Read-only: cluster information
kubectl cluster-info

# Read-only: list nodes
kubectl get nodes -o wide

# Read-only: list namespaces
kubectl get namespaces

# Read-only: list pods
kubectl get pods -A

# Read-only: describe pod
kubectl describe pod <pod-name> -n <namespace>

# Read-only: view pod logs
kubectl logs <pod-name> -n <namespace>

# Read-only: view previous container logs
kubectl logs <pod-name> -n <namespace> --previous

# Read-only: list events
kubectl get events -A --sort-by=.lastTimestamp

# Modifying: restart deployment
kubectl rollout restart deployment <deployment-name> -n <namespace>

# Modifying: scale deployment
kubectl scale deployment <deployment-name> --replicas=<count> -n <namespace>

# Modifying: apply manifest
kubectl apply -f <manifest-file>
```

## 64. Kubernetes troubleshooting

| Symptom | Possible cause | Diagnostic command |
|---|---|---|
| Pod pending | Insufficient capacity, scheduling constraints, PVC pending | `kubectl describe pod` |
| CrashLoopBackOff | Application error, bad configuration, dependency failure | `kubectl logs --previous` |
| ImagePullBackOff | Wrong image, registry authentication, network issue | `kubectl describe pod` |
| Service unreachable | Selector mismatch, endpoint absent, port mismatch | `kubectl get endpoints` |
| Ingress failure | Ingress controller, DNS, TLS, backend service | `kubectl get ingress` |
| Node NotReady | Kubelet, network, resource pressure | `kubectl describe node` |
| OOMKilled | Memory limit too low or memory leak | `kubectl describe pod` |
| PVC pending | Storage class, capacity, access mode | `kubectl get pvc` |

## 65. Kubernetes security

- Use least-privilege RBAC.
- Avoid privileged containers unless justified.
- Run containers as non-root where possible.
- Use read-only root filesystems where possible.
- Scan images for vulnerabilities.
- Use image signing and admission controls where appropriate.
- Encrypt secrets at rest where supported.
- Use network policies.
- Enable audit logging.
- Restrict Kubernetes API access.
- Use separate namespaces and node pools for workload isolation.

# Part 16 — Database Operations

## 66. Database operational principles

Databases require special attention for consistency, performance, backup, security, and recovery.

| Area | Requirement |
|---|---|
| Backup | Regular backups and tested restores |
| Recovery | RPO and RTO defined |
| Security | Least privilege, encryption, network restriction |
| Performance | Monitor CPU, memory, I/O, connections, locks |
| High availability | Replication or failover where required |
| Change control | Schema changes reviewed and tested |
| Monitoring | Alerts for availability, latency, errors, capacity |

## 67. SQL Server operations

### 67.1 Common checks

```sql
-- Read-only: SQL Server version
SELECT @@VERSION;

-- Read-only: database list
SELECT name, state_desc FROM sys.databases;

-- Read-only: active sessions
SELECT session_id, login_name, host_name, program_name, status
FROM sys.dm_exec_sessions;

-- Read-only: database file usage
SELECT DB_NAME(database_id) AS database_name,
       name AS logical_name,
       size * 8 / 1024 AS size_mb
FROM sys.master_files;
```

### 67.2 SQL Server troubleshooting

| Symptom | Checks |
|---|---|
| Connection failure | SQL service, port 1433, firewall, authentication |
| Slow queries | Query plans, blocking, indexes, statistics |
| High CPU | Active queries, missing indexes, parallelism |
| High memory | Memory grants, buffer pool, OS memory |
| Disk latency | IOPS, throughput, queue depth |
| Full transaction log | Log backup, recovery model, long-running transaction |
| Backup failure | Agent, permissions, storage, network |

## 68. PostgreSQL operations

```bash
# Read-only: PostgreSQL version
psql --version

# Read-only: connect and list databases
psql -U <username> -h <hostname> -c "\l"

# Read-only: active connections
psql -U <username> -h <hostname> -c "SELECT * FROM pg_stat_activity;"

# Read-only: database size
psql -U <username> -h <hostname> -c "SELECT pg_size_pretty(pg_database_size('<database-name>'));"
```

## 69. MySQL operations

```bash
# Read-only: MySQL version
mysql --version

# Read-only: connect
mysql -u <username> -p -h <hostname>

# Read-only: list databases
SHOW DATABASES;

# Read-only: active connections
SHOW PROCESSLIST;

# Read-only: database size
SELECT table_schema,
       ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb
FROM information_schema.tables
GROUP BY table_schema;
```

# Part 17 — Advanced Security Operations

## 70. Vulnerability management

### 70.1 Lifecycle

1. Discover assets.
2. Scan vulnerabilities.
3. Prioritize findings.
4. Assign ownership.
5. Remediate or accept risk.
6. Validate remediation.
7. Report and track.

### 70.2 Prioritization model

| Factor | High priority |
|---|---|
| Exposure | Internet-facing |
| Severity | Critical or high |
| Exploitability | Known exploitation |
| Asset criticality | Tier 1 |
| Compensating controls | Absent |
| Compliance | Regulatory requirement |

## 71. Secrets management

| Practice | Requirement |
|---|---|
| No secrets in code | Store secrets in vault or secret manager |
| No secrets in pipeline logs | Mask sensitive output |
| Rotation | Rotate credentials according to policy |
| Least privilege | Grant only required secret access |
| Audit | Log secret access |
| Break-glass | Secure emergency access process |

## 72. Encryption and certificates

### 72.1 Encryption layers

| Layer | Examples |
|---|---|
| Data in transit | TLS, IPsec, SSH |
| Data at rest | Disk encryption, database encryption, storage encryption |
| Key management | Cloud KMS, HSM, customer-managed keys |
| Application encryption | Field-level or application-level encryption |

### 72.2 Certificate lifecycle

1. Inventory certificates.
2. Monitor expiry.
3. Request renewal.
4. Validate certificate chain.
5. Deploy certificate.
6. Test endpoint.
7. Revoke old certificate where appropriate.
8. Update documentation.

# Part 18 — Operational Runbooks

## 73. Server build runbook

```text
Server Build Runbook

1. Request details
2. Approvals
3. Network preparation
4. Image selection
5. VM deployment
6. OS configuration
7. Security baseline
8. Monitoring installation
9. Backup configuration
10. Application installation
11. Validation
12. CMDB registration
13. Handover
```

## 74. Patching runbook

```text
Patching Runbook

1. Identify patch scope
2. Review vulnerabilities and risk
3. Confirm maintenance window
4. Notify stakeholders
5. Take backup or snapshot
6. Apply patches
7. Reboot if required
8. Validate services
9. Validate monitoring
10. Close change
```

## 75. Certificate renewal runbook

```text
Certificate Renewal Runbook

1. Identify expiring certificate
2. Confirm certificate owner
3. Generate CSR or use managed renewal
4. Validate domain control
5. Issue certificate
6. Install certificate
7. Update service binding
8. Restart service if required
9. Validate HTTPS endpoint
10. Update inventory
```

## 76. Backup failure runbook

```text
Backup Failure Runbook

1. Identify failed job
2. Review error message
3. Check agent status
4. Check credentials
5. Check storage capacity
6. Check network connectivity
7. Check application consistency requirements
8. Correct root cause
9. Rerun backup
10. Validate recovery point
11. Document incident
```

# Part 19 — Extended Enterprise Scenarios

## 77. Scenario: File server migration

### Requirement

Migrate an on-premises Windows file server to Azure Files or AWS FSx while preserving permissions and minimizing downtime.

### Approach

1. Inventory shares, permissions, quotas, and data volume.
2. Identify dependent applications and users.
3. Choose target platform.
4. Establish connectivity.
5. Perform initial data copy.
6. Perform incremental synchronization.
7. Validate permissions and access.
8. Cut over DNS or UNC path.
9. Retain source for rollback.
10. Validate backup and monitoring.

### Validation

- [ ] Users can access shares
- [ ] Permissions are correct
- [ ] Applications can read/write
- [ ] Backup is configured
- [ ] Monitoring is operational
- [ ] Performance meets requirement
- [ ] Rollback remains possible

## 78. Scenario: Linux web application migration

### Requirement

Migrate a Linux web application from on-premises to cloud with minimal downtime.

### Architecture

```text
Load balancer
└── Web tier
    └── Application tier
        └── Database tier
```

### Steps

1. Discover application stack.
2. Build target infrastructure.
3. Migrate application code.
4. Migrate configuration and secrets.
5. Migrate database.
6. Configure TLS certificates.
7. Configure monitoring.
8. Test in staging.
9. Cut over DNS.
10. Validate and monitor.

## 79. Scenario: Kubernetes migration

### Requirement

Migrate containerized workloads to managed Kubernetes.

### Steps

1. Inventory containers, images, manifests, and dependencies.
2. Assess image registry and security requirements.
3. Build target cluster.
4. Configure identity and networking.
5. Deploy workloads using IaC.
6. Migrate configuration and secrets.
7. Validate application functionality.
8. Configure autoscaling and monitoring.
9. Cut over traffic.
10. Decommission source when safe.

# Part 20 — Extended RAG Optimization

## 80. Retrieval query examples

| User question | Best matching sections |
|---|---|
| How do I troubleshoot a Linux VM with high CPU? | Linux performance troubleshooting |
| How do I migrate VMware VMs to Azure? | Azure migration scenario |
| How do I configure AWS Transit Gateway? | AWS networking |
| How do I secure AKS? | Azure Kubernetes Service |
| How do I recover a failed backup? | Backup failure runbook |
| How do I design a multi-region DR solution? | Multi-region DR scenario |
| How do I create an Azure resource group? | Azure CLI reference |
| How do I check AD replication health? | Active Directory operations |

## 81. Retrieval quality controls

- Use metadata filters for cloud provider and operating system.
- Prefer recent reviewed chunks.
- Avoid retrieving unrelated provider sections.
- Include source citations in answers.
- Detect destructive commands and require confirmation.
- Maintain a change log for corpus updates.
- Evaluate retrieval accuracy with test questions.

## 82. Corpus maintenance

| Frequency | Activity |
|---|---|
| Monthly | Review new cloud features and deprecations |
| Quarterly | Validate commands and documentation links |
| Semi-annually | Review architecture standards |
| Annually | Full knowledge-base review |
| After major incident | Add lessons learned |
| After migration | Add migration learnings |

# Part 21 — Additional Enterprise Standards

## 83. Naming standards

| Resource | Pattern |
|---|---|
| Resource group | `<org>-<env>-<app>-rg-<region>-<seq>` |
| Virtual network | `<org>-<env>-<app>-vnet-<region>` |
| Subnet | `<org>-<env>-<app>-snet-<purpose>` |
| Virtual machine | `<org>-<env>-<app>-<role>-<region>-<seq>` |
| Storage account | `<org><env><app><purpose><seq>` |
| Kubernetes cluster | `<org>-<env>-<app>-aks/eks/gke-<region>` |
| Key vault | `<org>-<env>-<app>-kv-<region>` |

## 84. Environment standards

| Environment | Purpose | Change control |
|---|---|---|
| Development | Active development | Low |
| Test | Functional and integration testing | Medium |
| Staging | Production-like validation | High |
| Production | Business operations | Full change control |

## 85. Operational handover checklist

- [ ] Architecture documentation
- [ ] Network diagrams
- [ ] CMDB records
- [ ] Access model
- [ ] Monitoring dashboards
- [ ] Alert runbooks
- [ ] Backup policies
- [ ] DR procedures
- [ ] Incident contacts
- [ ] Change history
- [ ] Known issues
- [ ] Support model
- [ ] Cost owner
- [ ] Security owner

# Part 22 — Final Assistant Guardrails

## 86. Destructive action policy

The assistant must treat the following as destructive or high-risk:

- Deleting VMs, disks, databases, storage, or backups
- Terminating instances
- Deleting Kubernetes namespaces or persistent volumes
- Running `terraform destroy`
- Removing IAM roles or policies
- Modifying firewall rules broadly
- Changing DNS records
- Deleting files or logs
- Modifying AD objects
- Changing production database schemas

Before any destructive action, the assistant must:

1. Confirm the exact resource.
2. Confirm the environment.
3. Explain impact.
4. Require explicit approval.
5. Provide rollback plan.
6. Recommend backup or snapshot where applicable.

## 87. Answering unknown questions

If the assistant lacks sufficient information, it should:

- Ask for cloud provider, environment, OS, and application details.
- Avoid guessing service limits or pricing.
- Recommend official documentation.
- Provide a safe diagnostic approach.
- Distinguish assumptions from verified facts.
- Escalate destructive or ambiguous production changes.

## 88. Knowledge-base completion statement

This knowledge base is designed to ground a local RAG assistant for enterprise multi-cloud infrastructure operations. It should be refreshed regularly and supplemented with organization-specific standards, approved architectures, CMDB data, runbooks, security baselines, and operational lessons learned.
