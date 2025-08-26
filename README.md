# Airflow Dags
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-10-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->

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

<details><summary><a>
  <h3>1.17 - 2025-08-27</h3> <small>[ Click to expand ]</small>
</a></summary>

UK
- Change PVlive logs to INFO
- Remove old Satellite consumer
- Update blend logs to INFO

India
- Update to use new satellite consumer
- Forecast app to `1.1.16` to use new satellite consumer

</details>

<details><summary><a>
  <h3>1.16 - 2025-08-19</h3> <small>[ Click to expand ]</small>
</a></summary>

UK
- Remove old PVlive container
- Update satellite extra latest zarr method
- UK-PVnet-app to `2.6.12` and use new satellite consumer
- Cloudcasting app to `0.0.10` and use new satellite consumer

NL
- Update site forecast to `1.1.16`, use new satellite consumer

</details>

<details><summary><a>
  <h3>1.15 - 2025-08-12</h3> <small>[ Click to expand ]</small>
</a></summary>

NL
- Update site forecast to `1.1.11`, works with backup satellite data

</details>

<details><summary><a>
  <h3>1.14 - 2025-08-11</h3> <small>[ Click to expand ]</small>
</a></summary>

UK
- PVNet app `2.6.8`, Update Pvnet and PVnet summation models
- PVLive Consumer gets 12 hours of history. 
- Add Fix ice chunk location for new satellite consumer
- Add 0 degree satellite in new satellite consumer

NL
- Update site forecast to `1.1.10`, read for new satellite consumer
- Save ML batches

India
- Run RUVNL forecast every hour
- Remove PV from site India-forecast-app, PV is now run in site-forecast-app

</details>

<details><summary><a>
  <h3>1.13 - 2025-07-29</h3> <small>[ Click to expand ]</small>
</a></summary>

India
- Update site forecast app to `1.1.7` with forecast times fix.

NL
- Update site forecast app to `1.1.7` with forecast times fix.

</details>

<details><summary><a>
  <h3>1.12 - 2025-07-28</h3> <small>[ Click to expand ]</small>
</a></summary>

All: Add links to airflow in slack messages
UK:
- Add new satellite consumer
- Change Site API not to check generation values

</details>

<details><summary><a>
  <h3>1.11 - 2025-07-23</h3> <small>[ Click to expand ]</small>
</a></summary>

All: better slack messages with alerts 

India
- New site forecast app to `1.1.6` with satellite data scale and night clipping fixes.
- Better alerting for RUVNL consumer. 

NL
- site forecast app to `1.1.5` to include night clipping fix.

</details>

<details><summary><a>
  <h3>1.10 - 2025-07-17</h3> <small>[ Click to expand ]</small>
</a></summary>

India
- Database migration is needed
- Add checks on API
- RUVNL consumer to `1.2.0`, use new database schema. 
- Site Forecast to `1.2.0`, use new database schema.

UK
- Site Database migration is needed
- Add checks on site API
- PV Consumer to `1.2.1`, use new database schema.
- PV Site Forecast to `1.1.0`, use new database schema.
- Reset old ec2 instances for UK National API.

NL
- Database migration is needed (Same as UK Sites)
- Ned NL consumer to `1.2.1`, use new database schema.
- Forecast to `1.1.0`, use new database schema.

</details>

<details><summary><a>
  <h3>1.9 - 2025-07-10</h3> <small>[ Click to expand ]</small>
</a></summary>

- Add country flags to slack messages
- PVNet to `2.6.3`, save forecast horizon
- NL forecast to `0.0.22`
- NedNL Consumer to `1.1.14` and run every 30 minutes
- Upgrade NedNl Forecast to `1.1.14`

</details>

<details><summary><a>
  <h3>1.8 - 2025-07-01</h3> <small>[ Click to expand ]</small>
</a></summary>

- Remove PVLive on-prem consumer
- Blend upgrade from `1.1.4` to `1.1.5`, add horizon_minutes to database
- NL forecast from `0.0.11` to `0.0.20`, NL 48 hour forecast and runs every hour
- Metrics upgrade from `1.3.0` to `1.3.4`, big speed up
- Upgrade site database clean up to `1.0.31`, dont delete NL site
- Upgrade uk site forecast `1.0.32`, only uk sites

</details>

<details><summary><a>
  <h3>1.7 - 2025-06-16</h3> <small>[ Click to expand ]</small>
</a></summary>

- Update UK NWP consumer from `v1.1.21` to `v1.1.26`
- Update UK NWP consumer in NL from `v1.1.23` to `v1.1.26`
- Add India AD forecast V2
- Run NL forecast every hour

</details>

<details><summary><a>
  <h3>1.6 - 2025-06-09</h3> <small>[ Click to expand ]</small>
</a></summary>

- Add new API check for national/forecast
- Update UK PVnet app from `2.5.22` to `2.6.0` - new model for new gsps areas.

</details>

<details><summary><a>
  <h3>1.5</h3> <small>[ Click to expand ]</small>
</a></summary>

- Add new API checks for UK GSP and National
- Update blend service from `1.1.3` to `1.1.4` - improved logging
- UK PVnet app updated to `2.5.18` -> `2.5.22` - Don't regrid ECMWF for DA model and get ready for new GSPs.
- New NL Forecasts
- Metrics upgrade from `1.2.23` to `1.3.0`, major speed upgrade for ME
- Scale UK GSP and National API to 2 ec2 instances

</details>

<details><summary><a>
  <h3>1.4</h3> <small>[ Click to expand ]</small>
</a></summary>

- Add new NL consumer for Ned-NL forecast, and use version `1.1.12`
- Add new NL nwp consumer for ECMWF
- Pull both on and new GSPs from PVLive
- PVnet app updated to `2.5.16` -> `2.5.18`, fixes git version
- Upgrade blend service to `1.1.3` - [fixes version issue](https://github.com/openclimatefix/uk-pv-forecast-blend/issues/48),
note small data migration is needed, where we need to set created_utc times for the ml models. Also API should be upgraded to `1.5.93`
- Update slack warning maessage for PVnet app
- Upgrade PVsite database clean up to `1.0.30`

</details>

<details><summary><a>
  <h3>1.3</h3> <small>[ Click to expand ]</small>
</a></summary>

- Adding a new NL consumer
- Update pvnet slack error/warning message logic 
- Update slack error messages/links for uk and india satellite consumers

</details>

<details><summary><a>
  <h3>1.2</h3> <small>[ Click to expand ]</small>
</a></summary>

- Cloudcasting inputs on the intraday forecaster in dev
- Update forecast_blend `1.0.8` -> `1.1.1`
- Update metrics `1.2.22` -> `1.2.23`
- Add DAG to calculate ME

</details>

<details><summary><a>
  <h3>1.1</h3> <small>[ Click to expand ]</small>
</a></summary>

- Update PVLive consumer to use on prem server - from `1.2.5` to `1.2.6`. 
- Trigger blend service, even if PVnet fails
- Tidy PVnet App docs -`2.5.15` to `2.5.16`
- India forecast app to save probabilistic values - `1.1.34` to `1.1.39`
- Upgrade Cloudcasting app - `0.0.7` to `0.0.8`

</details>

<details><summary><a>
  <h3>1.0</h3> <small>[ Click to expand ]</small>
</a></summary>

Initial release

</details>

## How to make a release to production

Releases to development are made automatically when a PR is merged to `main`. 
For production releases, we try to bundle a few changes together in a minor version release. 
Once we are ready to release to production we follow the next steps

- Create a new branch called `X.Y-release`
- Update the readme, with the changes made in this new release. This can be done by compare tags, for [example](https://github.com/openclimatefix/airflow-dags/compare/v1.2.0...v1.2.7). 
- Create a PR from `X.Y-release` to `main` and get this approved. Note that currently the CI won't run
for README changes.
- When merging this PR, add `#minor` to the PR `Extended description` under `Commit message`. 
- Merge the PR to `main` and delete the branch, this will create the tag `X.Y`. 
- Under Actions, go to `Deploy DAGs`, click on `Run workflow` and select the `X.Y` tag. This will then need to be approved. 

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
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/devsjc"><img src="https://avatars.githubusercontent.com/u/47188100?v=4?s=100" width="100px;" alt="devsjc"/><br /><sub><b>devsjc</b></sub></a><br /><a href="https://github.com/openclimatefix/airflow-dags/commits?author=devsjc" title="Code">💻</a> <a href="#research-devsjc" title="Research">🔬</a> <a href="https://github.com/openclimatefix/airflow-dags/pulls?q=is%3Apr+reviewed-by%3Adevsjc" title="Reviewed Pull Requests">👀</a> <a href="#ideas-devsjc" title="Ideas, Planning, & Feedback">🤔</a> <a href="https://github.com/openclimatefix/airflow-dags/commits?author=devsjc" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/peterdudfield"><img src="https://avatars.githubusercontent.com/u/34686298?v=4?s=100" width="100px;" alt="Peter Dudfield"/><br /><sub><b>Peter Dudfield</b></sub></a><br /><a href="https://github.com/openclimatefix/airflow-dags/commits?author=peterdudfield" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/dfulu"><img src="https://avatars.githubusercontent.com/u/41546094?v=4?s=100" width="100px;" alt="James Fulton"/><br /><sub><b>James Fulton</b></sub></a><br /><a href="https://github.com/openclimatefix/airflow-dags/commits?author=dfulu" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Sukh-P"><img src="https://avatars.githubusercontent.com/u/42407101?v=4?s=100" width="100px;" alt="Sukhil Patel"/><br /><sub><b>Sukhil Patel</b></sub></a><br /><a href="https://github.com/openclimatefix/airflow-dags/commits?author=Sukh-P" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/yuvraajnarula"><img src="https://avatars.githubusercontent.com/u/49155095?v=4?s=100" width="100px;" alt="Yuvraaj Narula"/><br /><sub><b>Yuvraaj Narula</b></sub></a><br /><a href="https://github.com/openclimatefix/airflow-dags/commits?author=yuvraajnarula" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/zakwatts"><img src="https://avatars.githubusercontent.com/u/47150349?v=4?s=100" width="100px;" alt="Megawattz"/><br /><sub><b>Megawattz</b></sub></a><br /><a href="https://github.com/openclimatefix/airflow-dags/commits?author=zakwatts" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/EricS02"><img src="https://avatars.githubusercontent.com/u/124088002?v=4?s=100" width="100px;" alt="Erics"/><br /><sub><b>Erics</b></sub></a><br /><a href="https://github.com/openclimatefix/airflow-dags/commits?author=EricS02" title="Code">💻</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="http://www.linkedin.com/in/ram-from-tvl"><img src="https://avatars.githubusercontent.com/u/114728749?v=4?s=100" width="100px;" alt="Ramkumar R"/><br /><sub><b>Ramkumar R</b></sub></a><br /><a href="https://github.com/openclimatefix/airflow-dags/commits?author=ram-from-tvl" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/KamathAnjali"><img src="https://avatars.githubusercontent.com/u/178002997?v=4?s=100" width="100px;" alt="Anjali Kamath"/><br /><sub><b>Anjali Kamath</b></sub></a><br /><a href="#content-KamathAnjali" title="Content">🖋</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Pradyumn-cloud"><img src="https://avatars.githubusercontent.com/u/183612033?v=4?s=100" width="100px;" alt="Pradyumn Prasad"/><br /><sub><b>Pradyumn Prasad</b></sub></a><br /><a href="https://github.com/openclimatefix/airflow-dags/commits?author=Pradyumn-cloud" title="Code">💻</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

---

*Part of the [Open Climate Fix](https://github.com/orgs/openclimatefix/people) community.*

[![OCF Logo](https://cdn.prod.website-files.com/62d92550f6774db58d441cca/6324a2038936ecda71599a8b_OCF_Logo_black_trans.png)](https://openclimatefix.org)

