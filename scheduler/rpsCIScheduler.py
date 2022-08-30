# import rankerConfig
import time
import numpy as np
import sys
import configparser
import os
from pathlib import Path
from google.cloud import datastore
from baselineSlackAnalysis import baselineSlackAnalysis
from rpsMultiVMSolver import rpsOffloadingSolver
from Estimator import Estimator
from getInvocationRate import InvocationRate
import sys


class CIScheduler:
    def __init__(self, triggerType):
        path = str(Path(os.path.dirname(os.path.abspath(__file__))))+"/rankerConfig.ini"
        self.config = configparser.ConfigParser()
        self.config.read(path)
        self.rankerConfig = self.config["settings"]
        self.workflow = self.rankerConfig["workflow"]
        x = Estimator(self.workflow)
        self.invocationRate = InvocationRate(self.workflow)
        # self.rates = invocationRate.getRPS()
        x.getCost()
        x.getPubSubMessageSize()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(Path(os.path.dirname(os.path.abspath(__file__)))) +"/key/schedulerKey.json"
        self.datastore_client = datastore.Client()
        kind = "routingDecision"
        name = self.workflow
        routing_key = self.datastore_client.key(kind, name)
        self.routing = self.datastore_client.get(key=routing_key)
        self.decisionModes = (self.rankerConfig["decisionMode"]).split()
        self.mode = self.rankerConfig["mode"]
        self.alpha = float(self.rankerConfig["statisticalParameter"])
        self.rps = float(self.rankerConfig["rps"])
        resources = open(str(Path(os.path.dirname(os.path.abspath(__file__)))) + "/resources.txt", "r")
        Lines = resources.readlines()
        cpus = Lines[0].split()
        memories = Lines[1].split()
        self.availableResources = []
        assert len(cpus) == len(
            memories
        ), "Both number of cores and memory should be provided for each VM"
        for i in range(len(cpus)):
            dict = {}
            dict["cores"] = float(cpus[i])
            dict["mem_mb"] = float(memories[i])
            self.availableResources.append(dict)
        print("AvailableResources ===", self.availableResources)
        # self.availableResources = rankerConfig.availResources
        self.toleranceWindow = int(self.rankerConfig["toleranceWindow"])
        self.suggestBestOffloadingMultiVM(triggerType)

    def suggestBestOffloadingMultiVM(self, triggerType):
        if triggerType == "highLoad":
            prevPercentage = self.routing["active"]
            match prevPercentage:
                case "25":
                    self.routing["active"] = "50"
                    self.datastore_client.put(self.routing)
                case "50":
                    self.routing["active"] = "75"
                    self.datastore_client.put(self.routing)
                case "75":
                    self.routing["active"] = "95"
                    self.datastore_client.put(self.routing)
                case "95":
                    self.resolveOffloadingSolutions()
                case other:
                    print("Unknown percentile")
        elif triggerType == "lowLoad":
            prevPercentage = self.routing["active"]
            match prevPercentage:
                case "95":
                    self.routing["active"] = "75"
                    self.datastore_client.put(self.routing)
                case "75":
                    self.routing["active"] = "50"
                    self.datastore_client.put(self.routing)
                case "50":
                    self.routing["active"] = "25"
                    self.datastore_client.put(self.routing)
                case "25":
                    self.resolveOffloadingSolutions()
                case other:
                    print("Unknown percentile")
        elif triggerType == "resolve":
            self.resolveOffloadingSolutions()
        else:
            print("Unknown trigger type!")

    def resolveOffloadingSolutions(self):
        rates = self.invocationRate.getRPS()
        decisions = []
        for percent in rates.keys():
            rate = rates[percent]
            for decisionMode in self.decisionModes:
                solver = rpsOffloadingSolver(
                    self.workflow, self.mode, decisionMode, self.toleranceWindow, rate, False
                )
                x = solver.suggestBestOffloadingMultiVM(
                    availResources=self.availableResources,
                    alpha=self.alpha,
                    verbose=True,
                )
                print("Decision for case: {}:{}".format(decisionMode, x))
                decisions.append(x)
            finalDecision = np.mean(decisions, axis=0)
            finalDecision = finalDecision / 100
            capArray = np.zeros(len(finalDecision))
            for i in range(len(capArray)):
                capArray[i] = np.full(len(finalDecision[i]), 0.9)
                finalDecision[i] = np.multiply(finalDecision[i], capArray[i])
            finalDecision = list(finalDecision)
            for function in range(len(finalDecision)):
                finalDecision[function] = list(finalDecision[function])
            self.routing["routing" + "_" + str(percent)] = str(finalDecision)
            print("Final Decision: {}".format(list(finalDecision)))
        self.routing["active"] = "50"
        self.datastore_client.put(self.routing)


if __name__ == "__main__":
    start_time = time.time()
    #Added by mohamed to allow locking
    if os.path.exists(str(Path(os.path.dirname(os.path.abspath(__file__))))+'/lock.txt'):
        print("LOCK EXISTSSS!!")
        exit()
    with open(str(Path(os.path.dirname(os.path.abspath(__file__))))+"/lock.txt","w") as f:
        f.write("lock")
        f.close
    print("LOCK CREATED!!!")
    # triggerType = "resolve"
    triggerType = sys.argv[1]
    solver = CIScheduler(triggerType)
    os.remove(str(Path(os.path.dirname(os.path.abspath(__file__))))+"/lock.txt")
    print("LOCK removed-> search for lock file:", os.path.exists(str(Path(os.path.dirname(os.path.abspath(__file__))))+'/lock.txt'))
    print("--- %s seconds ---" % (time.time() - start_time))


