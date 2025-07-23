"""Helper functions that handle S3 files."""

import shutil
import tempfile

import icechunk
import xarray as xr
from airflow.decorators import task
from airflow.providers.amazon.aws.hooks.s3 import S3Hook


@task(task_id="determine_latest_zarr")
def determine_latest_zarr(bucket: str, prefix: str) -> None:
    """Determins the zarr folder in a bucket that was most recently created."""
    s3hook = S3Hook(aws_conn_id=None)  # Use Boto3 default connection strategy
    # Get a list of all the non-latest zarrs in the bucket prefix
    prefixes = s3hook.list_prefixes(bucket_name=bucket, prefix=prefix + "/", delimiter="/")
    zarrs = sorted(
        [p for p in prefixes if p.endswith(".zarr/") and "latest" not in p],
        reverse=True,
    )
    # Get the size of the most recent zarr and the latest.zarr zarr
    s3bucket = s3hook.get_bucket(bucket_name=bucket)
    size_old, size_new = (0, 0)
    if len(zarrs) == 0:
        s3hook.log.info("No non-latest zarrs found in bucket, exiting")
        return

    for obj in s3bucket.objects.filter(Prefix=zarrs[0]):
        size_new += obj.size

    if prefix + "/latest.zarr/" in prefixes:
        for obj in s3bucket.objects.filter(Prefix=prefix + "/latest.zarr/"):
            size_old += obj.size

    # If the sizes are different, create a new latest.zarr
    s3hook.log.info(f"size_old={size_old}, size_new={size_new}")
    if size_old != size_new and size_new > 500 * 1e3:  # Expecting at least 500KB
        # delete latest.zarr
        s3hook.log.info(f"Deleting {prefix}/latest.zarr/")
        if prefix + "/latest.zarr/" in prefixes:
            s3hook.log.debug(f"Deleting {prefix}/latest.zarr/")
            keys_to_delete = s3hook.list_keys(bucket_name=bucket, prefix=prefix + "/latest.zarr/")
            s3hook.delete_objects(bucket=bucket, keys=keys_to_delete)

        # move latest zarr file to latest.zarr using s3 batch jobs
        s3hook.log.info(f"Creating {prefix}/latest.zarr/")

        # Copy the new latest.zarr
        s3hook.log.info(f"Copying {zarrs[0]} to {prefix}/latest.zarr/")
        source_keys = s3hook.list_keys(bucket_name=bucket, prefix=zarrs[0])
        for key in source_keys:
            s3hook.copy_object(
                source_bucket_name=bucket,
                source_bucket_key=key,
                dest_bucket_name=bucket,
                dest_bucket_key=prefix + "/latest.zarr/" + key.split(zarrs[0])[-1],
            )

    else:
        s3hook.log.info("No changes to latest.zarr required")


@task(task_id="extract_latest_zarr")
def extract_latest_zarr(bucket: str, prefix: str, window_mins: int, cadence_mins: int) -> None:
    """Extracts a latest.zarr file from an icechunk store in a bucket."""
    s3hook = S3Hook(aws_conn_id=None)  # Use Boto3 default connection strategy
    creds = s3hook.get_credentials()

    storage = icechunk.s3_storage(
        bucket=bucket,
        prefix=prefix,
        region=s3hook.region_name,
        access_key_id=creds.access_key,
        secret_access_key=creds.secret_key,
        session_token=creds.token,
    )
    repo = icechunk.Repository.open(storage=storage)
    session = repo.readonly_session(branch="main")
    store_ds = xr.open_zarr(store=session.store, consolidated=False)
    desired_image_num: int = window_mins // cadence_mins
    s3hook.log.info(f"Extracting latest zarr from {prefix} with window of {window_mins} minutes")
    with tempfile.TemporaryDirectory(suffix=".zarr") as tmpzarr:
        store_ds.isel(time=slice(-desired_image_num, None)).to_zarr(
            tmpzarr,
            mode="w",
            consolidated=True,
        )
        # Zip the zarr directory
        shutil.make_archive(
            base_name=tmpzarr + "/latest",
            root_dir=tmpzarr,
            base_dir=".",
            format="zip",
        )
        s3hook.load_file(
            filename=f"{tmpzarr}/latest.zip",
            bucket_name=bucket,
            replace=True,
            key=f"{prefix.rsplit('/', 1)[0]}/latest.zarr.zip",
        )
    s3hook.log.info(f"Extracted latest zarr to {bucket}/{prefix}/latest.zarr.zip")
