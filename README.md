# Airflow Dags

**Airflow pipelines for Open Climate Fix's production systems**
 
[![workflows badge](https://img.shields.io/github/actions/workflow/status/openclimatefix/airflow-dags/merged_ci.yml?label=workflow&color=FFD053)](https://github.com/openclimatefix/airflow-dags/actions/workflows/merged_ci.yml)
[![tags badge](https://img.shields.io/github/v/tag/openclimatefix/airflow-dags?include_prereleases&sort=semver&color=FFAC5F)](https://github.com/openclimatefix/airflow-dags/tags)
[![contributors badge](https://img.shields.io/github/contributors/openclimatefix/airflow-dags?color=FFFFFF)](https://github.com/openclimatefix/airflow-dags/graphs/contributors)
[![ease of contribution: medium](https://img.shields.io/badge/ease%20of%20contribution:%20medium-f4900c)](https://github.com/openclimatefix#how-easy-is-it-to-get-involved)


> [!Note]
> This repo is a migration of the `dags` folder from the
> [ocf-infrastructure](https://github.com/openclimatefix/ocf-infrastructure)
> repository. Commit history and authorship has not been preserved,
> so for previous iterations of the DAGs, see the original repository's history.

Many of OCF's production services run as batch pipelines managed by an Airflow deployment.
This repo defines those airflow DAGs that configure, version control, and test these pipelines,
and handles the deployment process.

## Releases

### 1.1.0

- Update PVLive consumer to use on prem server - from `1.2.5` to `1.2.6`. 
- Trigger blend service, even if PVnet fails
- Tidy PVnet App docs -`2.5.15` to `2.5.16`
- India forecast app to save probabilistic values - `1.1.34` to `1.1.39`
- Upgrade Cloudcasting app - `0.0.7` to `0.0.8`

### 1.0

Initial release


## Installation

Copy the `airflow_dags` folder into your `dags` location:
```bash
$ cp -r airflow_dags /path/to/airflow/dags
```

Or use the build webserver image in your containerized airflow deployment:
```bash
$ docker pull ghcr.io/openclimatefix/airflow-dags
```

## Example usage

See the docker-compose file in the
[ocf-infrastructure](https://github.com/openclimatefix/ocf-infrastructure)
repository. 

## Documentation

DAGs are defined in the `dags` folder, split into modules according to domain.
Each domain corresponds to a seperate deployment of airflow, and as such,
a distinct set of DAGs, hence some similarity or even duplication is expected. 

Functions, or custom operators, are found in the `plugins` folder.

## FAQ

### Can I change the name of a DAG?

Try to avoid it! The DAG name is how airflow identifies the DAG in the database.
If you change the name of a DAG, airflow will treat it as a new DAG.
This means that the old DAG will still be in the database, but it will not be updated or run. 

### Why move this here from ocf-infrastructure?

Because service running configuration isn't terraform configuration!
Terraform is usually used for setting up infrastructure - platform level resources like databases, networks, and VMs, and, Airflow itself.
The DAGs that airflow runs, and the versions of the services that those DAGs run, are implementation details,
and so should be stored in the config-as-code repository for airflow.

Furthermore, as a mostly Python organisation, having a top-level python only repo for Airflow increases it's accessibility to the wider team.  

## Development

### Linting and static type checking
 
This project uses [MyPy](https://mypy.readthedocs.io/en/stable/) for static type checking
and [Ruff](https://docs.astral.sh/ruff/) for linting.
Installing the development dependencies makes them available in your virtual environment.

Use them via:

```bash
$ python -m mypy .
$ python -m ruff check .
```

Be sure to do this periodically while developing to catch any errors early
and prevent headaches with the CI pipeline. It may seem like a hassle at first,
but it prevents accidental creation of a whole suite of bugs.

### Running the test suite

There are some additional dependencies to be installed for running the tests,
be sure to pass `--extra=dev` to the `pip install -e .` command when creating your virtualenv.
(Or use uv and let it do it for you!)

Run the unit tests with:

```bash
$ python -m unittest discover -s tests -p "test_*.py"
```
 
## Further reading

On the directory structure:
- The official [PyPA discussion](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) on 
"source" and "flat" layouts.


---

## Contributing and community

[![issues badge](https://img.shields.io/github/issues/openclimatefix/ocf-template?color=FFAC5F)](https://github.com/openclimatefix/ocf-template/issues?q=is%3Aissue+is%3Aopen+sort%3Aupdated-desc)

- PR's are welcome! See the [Organisation Profile](https://github.com/openclimatefix) for details on contributing
- Find out about our other projects in the [here](https://github.com/openclimatefix/.github/tree/main/profile)
- Check out the [OCF blog](https://openclimatefix.org/blog) for updates
- Follow OCF on [LinkedIn](https://uk.linkedin.com/company/open-climate-fix)


## Contributors

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

---

*Part of the [Open Climate Fix](https://github.com/orgs/openclimatefix/people) community.*

[![OCF Logo](https://cdn.prod.website-files.com/62d92550f6774db58d441cca/6324a2038936ecda71599a8b_OCF_Logo_black_trans.png)](https://openclimatefix.org)

