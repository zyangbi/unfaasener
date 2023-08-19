import unittest
import os
import json
from pathlib import Path
from rpsMultiVMSolver import rpsOffloadingSolver


class TestSolver(unittest.TestCase):

    workflow = "Text2SpeechCensoringWorkflow"
    mode = "cost"
    rps = 10

    def test_similar2prevdecision(self):
        jsonPath = (
            str(Path(os.path.dirname(os.path.abspath(__file__))).resolve().parents[0])
            + "/log-parser/get-workflow-logs/data/"
            + "TestCase3Workflow"
            + ".json"
        )
        with open(jsonPath, "r") as json_file:
            workflow_json = json.load(json_file)
        workflow_json["lastDecision_default"] = [[0.0], [0.0], [0.0], [0.0]]
        with open(jsonPath, "w") as json_file:
            json.dump(workflow_json, json_file)
        toleranceWindow = 0
        solver = rpsOffloadingSolver(
            workflow="TestCase3Workflow",
            mode=self.mode,
            decisionMode=None,
            toleranceWindow=toleranceWindow,
            rps=self.rps,
            testingFlag=True,
        )
        availResources = [{"cores": 1000, "mem_mb": 500000}]
        alpha = 1
        x = solver.suggestBestOffloadingMultiVM(
            availResources=availResources, alpha=alpha, verbose=True
        )
        self.assertEqual(x, [[0.0], [0.0], [0.0], [0.0]])

    def test_highPubsubCost(self):
        jsonPath = (
            str(Path(os.path.dirname(os.path.abspath(__file__))).resolve().parents[0])
            + "/log-parser/get-workflow-logs/data/"
            + "TestCaseWorkflow"
            + ".json"
        )
        workflow = "TestCaseWorkflow"
        with open(jsonPath, "r") as json_file:
            workflow_json = json.load(json_file)
        workflow_json["lastDecision_default"] = [[0.0], [0.0], [0.0], [0.0]]
        with open(jsonPath, "w") as json_file:
            json.dump(workflow_json, json_file)
        highPubsubSize = {"A": 10e10, "B": 10e10, "C": 10e10, "D": 10e10}
        with open(
            (
                (os.path.dirname(os.path.abspath(__file__)))
                + "/data/"
                + str(workflow)
                + "/"
                + "pubSubSize.json"
            ),
            "r",
        ) as json_file:
            prevPubSubSize = json.load(json_file)
        with open(
            (
                (os.path.dirname(os.path.abspath(__file__)))
                + "/data/"
                + str(workflow)
                + "/"
                + "pubSubSize.json"
            ),
            "w",
        ) as outfile:
            json.dump(highPubsubSize, outfile)
        toleranceWindow = 0
        solver = rpsOffloadingSolver(
            workflow=workflow,
            mode=self.mode,
            decisionMode=None,
            toleranceWindow=toleranceWindow,
            rps=self.rps,
            testingFlag=True,
        )
        availResources = [{"cores": 1000, "mem_mb": 500000}]
        alpha = 0
        x = solver.suggestBestOffloadingMultiVM(
            availResources=availResources, alpha=alpha, verbose=True
        )
        with open(
            (
                (os.path.dirname(os.path.abspath(__file__)))
                + "/data/"
                + str(workflow)
                + "/"
                + "pubSubSize.json"
            ),
            "w",
        ) as outfile:
            json.dump(prevPubSubSize, outfile)
        self.assertEqual(x, [[0.0], [100.0], [100.0], [100.0]])

    def test_highCost(self):
        jsonPath = (
            str(Path(os.path.dirname(os.path.abspath(__file__))).resolve().parents[0])
            + "/log-parser/get-workflow-logs/data/"
            + "TestCaseWorkflow"
            + ".json"
        )
        workflow = "TestCaseWorkflow"
        with open(jsonPath, "r") as json_file:
            workflow_json = json.load(json_file)
        workflow_json["lastDecision_default"] = [[0.0], [0.0], [0.0], [0.0]]
        with open(jsonPath, "w") as json_file:
            json.dump(workflow_json, json_file)
        with open(
            (
                (os.path.dirname(os.path.abspath(__file__)))
                + "/data/"
                + str(workflow)
                + "/"
                + "Costs.json"
            ),
            "r",
        ) as json_file:
            prevCosts = json.load(json_file)
        highCost = prevCosts.copy()
        for func in highCost.keys():
            highCost[func]["default"] = 10e10
        with open(
            (
                (os.path.dirname(os.path.abspath(__file__)))
                + "/data/"
                + str(workflow)
                + "/"
                + "Costs.json"
            ),
            "w",
        ) as outfile:
            json.dump(highCost, outfile)
        toleranceWindow = 0
        solver = rpsOffloadingSolver(
            workflow=workflow,
            mode=self.mode,
            decisionMode=None,
            toleranceWindow=toleranceWindow,
            rps=self.rps,
            testingFlag=True,
        )
        availResources = [{"cores": 1000, "mem_mb": 500000}]
        alpha = 0
        x = solver.suggestBestOffloadingMultiVM(
            availResources=availResources, alpha=alpha, verbose=True
        )
        with open(
            (
                (os.path.dirname(os.path.abspath(__file__)))
                + "/data/"
                + str(workflow)
                + "/"
                + "Costs.json"
            ),
            "w",
        ) as outfile:
            json.dump(prevCosts, outfile)
        self.assertEqual(x, [[0.0], [100.0], [100.0], [100.0]])

    def test_limitedVMResources(self):
        toleranceWindow = 0
        solver = rpsOffloadingSolver(
            workflow="TestCaseWorkflow",
            mode=self.mode,
            decisionMode=None,
            toleranceWindow=toleranceWindow,
            rps=self.rps,
            testingFlag=True,
        )
        availResources = [{"cores": 0, "mem_mb": 0}]
        alpha = 0
        x = solver.suggestBestOffloadingMultiVM(
            availResources=availResources, alpha=alpha, verbose=True
        )
        self.assertEqual(x, [[0.0], [0.0], [0.0], [0.0]])

    def test_rps(self):
        workflow = "TestCase3Workflow"
        toleranceWindow = 0
        jsonPath = (
            str(Path(os.path.dirname(os.path.abspath(__file__))).resolve().parents[0])
            + "/log-parser/get-workflow-logs/data/"
            + "TestCase3Workflow"
            + ".json"
        )
        with open(jsonPath, "r") as json_file:
            workflow_json = json.load(json_file)
        workflow_json["lastDecision_default"] = [
            [0.0, 0.0],
            [0.0, 0.0],
            [0.0, 0.0],
            [0.0, 0.0],
        ]
        with open(jsonPath, "w") as json_file:
            json.dump(workflow_json, json_file)
        solver = rpsOffloadingSolver(
            workflow=workflow,
            mode=self.mode,
            decisionMode=None,
            toleranceWindow=toleranceWindow,
            rps=self.rps,
            testingFlag=True,
        )
        availResources = [
            {"cores": 1, "mem_mb": 300},
            {"cores": 1, "mem_mb": 300},
        ]
        alpha = 0
        x = solver.suggestBestOffloadingMultiVM(
            availResources=availResources, alpha=alpha, verbose=True
        )
        self.assertIn(
            x,
            [
                #  Due to adding the mu factor set to 1 by default the decisions have changed
                [[0.0, 0.0], [1.0, 0.0], [49.0, 51.0], [2.0, 1.0]],
                [[0.0, 0.0], [6.0, 7.0], [50.0, 50.0], [6.0, 6.0]],
                [[0.0, 0.0], [6.0, 7.0], [51.0, 49.0], [6.0, 7.0]],
                [[0.0, 0.0], [8.0, 7.0], [50.0, 50.0], [5.0, 6.0]],
                [[0.0, 0.0], [7.0, 6.0], [49.0, 51.0], [7.0, 6.0]],
                [[0.0, 0.0], [7.0, 6.0], [50.0, 50.0], [6.0, 6.0]],
                [[0.0, 0.0], [7.0, 7.0], [50.0, 50.0], [6.0, 6.0]],
                [[0.0, 0.0], [12.0, 12.0], [50.0, 50.0], [1.0, 1.0]],
                [[0.0, 0.0], [1.0, 12.0], [50.0, 50.0], [12.0, 1.0]],
                [[0.0, 0.0], [12.0, 1.0], [50.0, 50.0], [1.0, 12.0]],
                [[0.0, 0.0], [7.0, 6.0], [50.0, 50.0], [6.0, 7.0]],
                [[0.0, 0.0], [6.0, 7.0], [50.0, 50.0], [7.0, 6.0]],
                [[0.0, 0.0], [14.0, 1.0], [48.0, 52.0], [1.0, 10.0]],
            ],
        )
        # self.assertEqual(x, [[0.0, 0.0], [6.0, 6.0], [50.0, 50.0], [7.0, 6.0]])

    def test_rps2(self):
        workflow = "TestCase3Workflow"
        toleranceWindow = 0
        jsonPath = (
            str(Path(os.path.dirname(os.path.abspath(__file__))).resolve().parents[0])
            + "/log-parser/get-workflow-logs/data/"
            + "TestCase3Workflow"
            + ".json"
        )
        with open(jsonPath, "r") as json_file:
            workflow_json = json.load(json_file)
        workflow_json["lastDecision_default"] = [
            [0.0],
            [0.0],
            [0.0],
            [0.0],
        ]
        with open(jsonPath, "w") as json_file:
            json.dump(workflow_json, json_file)
        solver = rpsOffloadingSolver(
            workflow=workflow,
            mode=self.mode,
            decisionMode=None,
            toleranceWindow=toleranceWindow,
            rps=self.rps,
            testingFlag=True,
        )
        availResources = [{"cores": 100, "mem_mb": 10000}]
        alpha = 0
        x = solver.suggestBestOffloadingMultiVM(
            availResources=availResources, alpha=alpha, verbose=True
        )
        self.assertEqual(x, [[0.0], [100.0], [100.0], [100.0]])

    def test_rps3(self):
        workflow = "TestCase3Workflow"
        toleranceWindow = 0
        jsonPath = (
            str(Path(os.path.dirname(os.path.abspath(__file__))).resolve().parents[0])
            + "/log-parser/get-workflow-logs/data/"
            + "TestCase3Workflow"
            + ".json"
        )
        with open(jsonPath, "r") as json_file:
            workflow_json = json.load(json_file)
        workflow_json["lastDecision_default"] = [
            [0.0, 0.0],
            [0.0, 0.0],
            [0.0, 0.0],
            [0.0, 0.0],
        ]
        with open(jsonPath, "w") as json_file:
            json.dump(workflow_json, json_file)
        solver = rpsOffloadingSolver(
            workflow=workflow,
            mode=self.mode,
            decisionMode=None,
            toleranceWindow=toleranceWindow,
            rps=self.rps,
            testingFlag=True,
        )
        availResources = [
            {"cores": 10000, "mem_mb": 300000},
            {"cores": 10000, "mem_mb": 300000},
        ]
        alpha = 0
        x = solver.suggestBestOffloadingMultiVM(
            availResources=availResources, alpha=alpha, verbose=True
        )
        self.assertEqual(x, [[0.0, 0.0], [50.0, 50.0], [50.0, 50.0], [50.0, 50.0]])


if __name__ == "__main__":
    unittest.main()
