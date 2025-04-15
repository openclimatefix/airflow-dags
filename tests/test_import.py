import unittest
from importlib.resources import files

import airflow.models


class TestImport(unittest.TestCase):
    """Validate DAG files using airflow's DagBag.

    This includes sanity checks e.g. do tasks have required arguments,
    are DAG ids unique & do DAGs have no cycles.
    """

    def test_import_dags_without_errors(self) -> None:
        dag_bag = airflow.models.DagBag(
            include_examples=False,
            dag_folder=str(files("airflow_dags").joinpath("dags")),
        )
        self.assertEqual(len(dag_bag.dags), 23)
        self.assertFalse(dag_bag.import_errors)

        # Additional project-specific checks can be added here, e.g. to enforce each DAG has a tag
        for dag_id, dag in dag_bag.dags.items():
            self.assertTrue(len(dag.tags) == 0, msg=f"{dag_id} in {dag.full_filepath} has tags")
            domain, function = dag_id.split("-")[0], dag_id.split("-")[1]
            self.assertIn(domain, ["uk", "india", "nl"])
            self.assertIn(function, ["consume", "forecast", "analysis", "manage"])

