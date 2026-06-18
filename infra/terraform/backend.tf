# Remote state in S3 with DynamoDB locking. The bucket and table are created by
# infra/terraform/bootstrap (apply that first). Values are intentionally left as
# placeholders and supplied at init time so the bucket name stays out of VCS:
#
#   terraform init \
#     -backend-config="bucket=<your-state-bucket>" \
#     -backend-config="key=flight-delay-predictor/terraform.tfstate" \
#     -backend-config="region=us-east-1" \
#     -backend-config="dynamodb_table=fdp-terraform-locks"

terraform {
  backend "s3" {
    encrypt = true
  }
}
