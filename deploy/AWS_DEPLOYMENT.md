# CogniSweep AWS Deployment

This is the AWS path that best matches the current deployment pack.

## Recommended First AWS Shape

Start with a single Amazon EC2 host running the existing Docker Compose VPS stack, backed by private Amazon S3 object storage:

| CogniSweep need | AWS service |
| --- | --- |
| Docker runtime | EC2 on Amazon Linux 2023 |
| HTTPS reverse proxy | Existing Caddy service in `docker-compose.vps.yml` |
| Uploaded files, media previews, generated exports | S3 private bucket with presigned URLs |
| AWS credentials | EC2 instance profile IAM role |
| DNS | Route 53 or your existing DNS provider |
| Edge protection | CloudFront plus AWS WAF, or an Application Load Balancer plus AWS WAF |
| Persistent local container data | EBS volume mounted on the EC2 host |
| Production database/auth tables | Keep the existing Supabase production setup unless you deliberately migrate persistence code |

This is simpler than ECS/App Runner for the first launch because this repo already includes multiple cooperating containers: Streamlit app, async receiver, worker supervisor, billing webhook receiver, and optional MT workers.

Use ECS/Fargate later when you want managed multi-instance scaling, ALB path routing, service autoscaling, ECR image promotion, and Secrets Manager/SSM Parameter Store managed runtime secrets.

## Region

Use the AWS region closest to your customers and payment/email providers. If your first users are primarily in India, `ap-south-1` is a reasonable starting default.

```dotenv
AWS_REGION=ap-south-1
```

## S3 Bucket

Create one private general-purpose S3 bucket for production files, for example:

```text
cognisweep-prod-files
```

Recommended bucket settings:

- Keep S3 Block Public Access enabled.
- Enable default server-side encryption.
- Enable bucket versioning if you want object rollback evidence.
- Do not use S3 static website hosting; CogniSweep is a server-side Streamlit app.

CogniSweep already uses `boto3` and generates signed URLs through `cloud_object_storage.py`, so the bucket does not need public object access.

## EC2 IAM Role

Prefer an EC2 instance profile over long-lived AWS keys in `deploy/.env.production`.

Attach a least-privilege policy like this to the EC2 role, replacing the bucket name:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CogniSweepListBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::cognisweep-prod-files"
    },
    {
      "Sid": "CogniSweepObjectAccess",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::cognisweep-prod-files/*"
    }
  ]
}
```

If you use a customer-managed KMS key for bucket encryption, also add the required KMS decrypt/encrypt permissions for that key.

## Production Env Values

Add these values to `deploy/.env.production`, using your real domain and bucket. Leave `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` unset when the EC2 instance role is attached correctly.

```dotenv
COGNISWEEP_DOMAIN=your-domain.com
COGNISWEEP_PUBLIC_BASE_URL=https://your-domain.com

COGNISWEEP_OBJECT_STORAGE_PROVIDER=s3
COGNISWEEP_OBJECT_STORAGE_ALLOW_PUBLIC_URLS=false
S3_BUCKET=cognisweep-prod-files
AWS_REGION=ap-south-1
# S3_ENDPOINT_URL is only for S3-compatible non-AWS providers. Leave it blank on AWS.

COGNISWEEP_ASYNC_WORKER_URL=http://errorsweep-async-receiver:8300/tasks
COGNISWEEP_BILLING_WEBHOOK_RECEIVER_URL=https://your-domain.com/webhooks/billing/razorpay

COGNISWEEP_BACKUP_PROVIDER=s3
COGNISWEEP_BACKUP_OBJECT_STORAGE_ENABLED=true
COGNISWEEP_WAF_PROVIDER=aws-waf

SELF_HOSTED_MT_ALLOW_PRIVATE_ENDPOINTS=true
SELF_HOSTED_MT_ACTIVE_ENGINES=indictrans2,opus
INDICTRANS2_ENDPOINT=http://errorsweep-indictrans2:8000/translate
OPUS_MT_ENDPOINT=http://errorsweep-opus-mt:8100/translate
```

The code and launch checks still accept legacy `ERRORSWEEP_*` aliases, but new AWS config should use `COGNISWEEP_*`.

## EC2 Host Setup

Launch an EC2 instance with:

- Amazon Linux 2023.
- Security group allowing inbound `80` and `443` from the internet.
- SSH restricted to your IP.
- The S3 IAM instance profile attached.
- An EBS volume sized for logs, temporary uploads, local queues, and MT model caches.

Install Docker on the host:

```bash
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
docker compose version
```

If `docker compose version` is not available, install the Docker Compose plugin before continuing.

Clone or copy the repo to the server, then create the production env file:

```bash
cd /opt
git clone <your-repo-url> cognisweep
cd /opt/cognisweep
cp deploy/.env.production.example deploy/.env.production
```

Fill `deploy/.env.production` with production secrets and the AWS values above. Do not commit this file.

## Deploy

Build and start the AWS-friendly VPS stack:

```bash
docker compose --env-file deploy/.env.production -f docker-compose.vps.yml build
docker compose --env-file deploy/.env.production -f docker-compose.vps.yml up -d
docker compose --env-file deploy/.env.production -f docker-compose.vps.yml ps
```

Caddy will request TLS certificates for `COGNISWEEP_DOMAIN`, so the domain must point to the EC2 public IP before the first public start.

## Edge: CloudFront And WAF

For first launch, direct DNS to the EC2 host is acceptable if the security group only exposes `80`/`443` and all launch checks pass.

For production hardening, put CloudFront and AWS WAF in front of the host:

- Create a CloudFront distribution with the EC2/Caddy HTTPS endpoint as a custom origin.
- Forward the headers needed by Streamlit, including WebSocket upgrade traffic.
- Attach an AWS WAF web ACL with managed baseline rules and rate limiting.
- Set `COGNISWEEP_PUBLIC_BASE_URL` to the final HTTPS domain customers use.

CloudFront supports WebSockets, which matters for Streamlit's live browser session.

## Verify

Run local launch checks before copying secrets to the host:

```powershell
python deploy/release_check.py --strict
python deploy/object_storage_check.py --env-file deploy/.env.production --strict
python deploy/launch_env_check.py --env-file deploy/.env.production --strict
```

Run live checks from the EC2 host after deployment:

```bash
python deploy/object_storage_check.py --env-file deploy/.env.production --probe-write --strict
python deploy/auth_session_check.py --env-file deploy/.env.production --probe-public-url --strict
python deploy/billing_check.py --env-file deploy/.env.production --probe-health --strict
python deploy/launch_rehearsal.py --env-file deploy/.env.production --include-os-env --probe-public --probe-workers --strict
docker compose --env-file deploy/.env.production -f docker-compose.vps.yml exec errorsweep-app python production_smoke_test.py --markdown --strict --probe-endpoints
docker compose --env-file deploy/.env.production -f docker-compose.vps.yml exec errorsweep-worker-supervisor python worker_supervisor.py --status
```

## Scaling Path

Move from EC2 Compose to ECS/Fargate when you need more than one app instance or managed rolling deploys:

- Push images to ECR.
- Split the app, async receiver, billing webhook, and workers into ECS services.
- Put the app and public webhook behind an Application Load Balancer.
- Keep S3 for object storage.
- Move secrets into Secrets Manager or SSM Parameter Store.
- Keep MT workers separate, especially if you move IndicTrans2/MADLAD to GPU EC2 capacity.

## AWS References

- EC2 IAM roles: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html
- S3 Block Public Access: https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html
- CloudFront WebSocket support: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-working-with.websockets.html
- AWS WAF: https://docs.aws.amazon.com/waf/latest/developerguide/waf-chapter.html
- ECS load balancing: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-load-balancing.html
