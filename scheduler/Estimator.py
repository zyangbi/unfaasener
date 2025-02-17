import json
import datetime
import os
import pandas as pd
import numpy as np
import math
from scipy.stats import ks_2samp, mannwhitneyu, chisquare

# from monitoring import monitoring
from pathlib import Path

# import rankerConfig
import configparser
from operator import itemgetter
from itertools import islice

pd.options.mode.chained_assignment = None


class Estimator:
    def __init__(self, workflow):
        path = (
            str(Path(os.path.dirname(os.path.abspath(__file__)))) + "/rankerConfig.ini"
        )
        self.config = configparser.ConfigParser()
        self.config.read(path)
        self.rankerConfig = self.config["settings"]
        self.workflow = workflow
        jsonPath = (
            str(Path(os.path.dirname(os.path.abspath(__file__))).resolve().parents[0])
            + "/log-parser/get-workflow-logs/data/"
            + self.workflow
            + ".json"
        )
        dfDir = Path(
            str(Path(os.path.dirname(os.path.abspath(__file__))).parents[0])
            + "/log-parser/get-workflow-logs/data/"
            + self.workflow
            + "/"
        )
        dfFilesNames = [
            file.name
            for file in dfDir.iterdir()
            if (
                (file.name.startswith("generatedDataFrame"))
                and (file.name.endswith(".pkl"))
            )
        ]
        # if os.path.isfile(
        #     str(Path(os.path.dirname(os.path.abspath(__file__))).resolve().parents[0])
        #     + "/log-parser/get-workflow-logs/data/"
        #     + self.workflow
        #     + "/generatedDataFrame.pkl"
        # ):
        if len(dfFilesNames) != 0:
            dfFilesNames = [a.replace(".pkl", "") for a in dfFilesNames]
            versions = [int((a.split(","))[1]) for a in dfFilesNames]
            lastVersion = max(versions)
            dataframePath = (
                str(
                    Path(os.path.dirname(os.path.abspath(__file__)))
                    .resolve()
                    .parents[0]
                )
                + "/log-parser/get-workflow-logs/data/"
                + self.workflow
                + "/generatedDataFrame,"
                + str(lastVersion)
                + ".pkl"
            )
            serverlessDF = pd.read_pickle(dataframePath)
        elif os.path.isfile(
            str(Path(os.path.dirname(os.path.abspath(__file__))).resolve().parents[0])
            + "/log-parser/get-workflow-logs/data/"
            + self.workflow
            + "/generatedDataFrame.csv"
        ):
            dataframePath = (
                str(
                    Path(os.path.dirname(os.path.abspath(__file__)))
                    .resolve()
                    .parents[0]
                )
                + "/log-parser/get-workflow-logs/data/"
                + self.workflow
                + "/generatedDataFrame.csv"
            )
            serverlessDF = pd.read_csv(dataframePath)
        else:
            print("Dataframe not found!")
            serverlessDF = None
        vmcachePath = (
            str(Path(os.path.dirname(os.path.abspath(__file__))).resolve().parents[0])
            + "/host-agents/execution-agent/data/cachedVMData.csv"
        )
        if os.path.isfile(vmcachePath):
            vmData = pd.read_csv(vmcachePath)
        else:
            vmData = None
        if vmData is not None:
            self.dataframe = pd.concat([serverlessDF, vmData], ignore_index=True)
        else:
            self.dataframe = serverlessDF

        with open(jsonPath, "r") as json_file:
            workflow_json = json.load(json_file)
        self.initFunc = workflow_json["initFunc"]
        self.workflowFunctions = workflow_json["workflowFunctions"]
        self.predecessors = workflow_json["predecessors"]
        self.successors = workflow_json["successors"]
        self.topics = workflow_json["topics"]
        self.windowSize = int(self.rankerConfig["windowSize"])
        # self.windowSize = 50
        self.memories = workflow_json["memory"]
        if os.path.exists(
            (
                (os.path.dirname(os.path.abspath(__file__)))
                + "/data/"
                + str(workflow)
                + "/"
                + "slackDurations.json"
            )
        ):
            with open(
                (
                    (os.path.dirname(os.path.abspath(__file__)))
                    + "/data/"
                    + str(workflow)
                    + "/"
                    + "slackDurations.json"
                ),
                "r",
                os.O_NONBLOCK,
            ) as outfile:
                self.slackDurationsDF = json.load(outfile)

    def prev_cost(self):

        with open(
            (os.path.dirname(os.path.abspath(__file__))) + "/data/" + "prevCost.json",
            "r",
        ) as json_file:
            workflow_json = json.load(json_file)
        return workflow_json

    def cost_estimator(self, NI, ET, GB):
        free_tier_invocations = 2000000
        free_tier_GB = 400000
        free_tier_GHz = 200000
        prev_Json = self.prev_cost()
        if prev_Json["NI"] > free_tier_invocations:
            free_tier_invocations = 0
        else:
            free_tier_invocations = free_tier_invocations - prev_Json["NI"]
        if prev_Json["GB-Sec"] > free_tier_GB:
            free_tier_GB = 0
        else:
            free_tier_GB = free_tier_GB - prev_Json["GB-Sec"]
        if prev_Json["GHz-Sec"] > free_tier_GHz:
            free_tier_GHz = 0
        else:
            free_tier_GHz = free_tier_GHz - prev_Json["GHz-Sec"]
        unit_price_invocation = 0.0000004
        unit_price_GB = 0.0000025
        unit_price_GHz = 0.0000100
        if GB == 0.125:
            Ghz = 0.2
        elif GB == 0.25:
            Ghz = 0.4
        elif GB == 0.5:
            Ghz = 0.8
        elif GB == 1:
            Ghz = 1.4
        elif GB == 2:
            Ghz = 2.4
        elif GB == 4:
            Ghz = 4.8
        elif GB == 8:
            Ghz = 4.8
        costInvoke = max(0, (NI - free_tier_invocations) * unit_price_invocation)
        costGB = max(
            0,
            (((NI * (math.ceil(ET / 100)) * 0.1 * GB) - free_tier_GB) * unit_price_GB),
        )
        costGhz = max(
            0,
            (
                ((NI * (math.ceil(ET / 100)) * 0.1 * Ghz) - free_tier_GHz)
                * unit_price_GHz
            ),
        )
        cost = costInvoke + costGB + costGhz
        return cost

    def getUpperBound(self, array):
        n = len(array)
        if n <= 30:
            # upperBound = 90
            upperBound = np.percentile(array, 75)
        else:
            sortedArray = np.sort(array)
            z = 1.96
            index = int(np.ceil(1 + ((n + (z * (np.sqrt(n)))) / 2)))
            upperBound = sortedArray[index]
        return upperBound

    def getMean(self, array):
        avg = np.mean(array)
        return avg

    # def getAverage(self, array):
    #     avg = array.mean()
    #     return avg

    def getLowerBound(self, array):
        n = len(array)
        if n <= 30:
            lowerBound = np.percentile(array, 25)
        else:
            sortedArray = np.sort(array)
            z = 1.96
            index = int(np.floor((n - (z * (np.sqrt(n)))) / 2))
            lowerBound = sortedArray[index]
        return lowerBound

    def getExecutionTime(self, host):
        exeTimes = {}
        decisionModes = (self.rankerConfig["decisionMode"]).split()
        for func in self.workflowFunctions:
            exeTimes[func] = {}
        for mode in decisionModes:
            for func in self.workflowFunctions:
                durations = []
                selectedInits = self.dataframe.loc[
                    (self.dataframe["function"] == func)
                    & (self.dataframe["host"] == host)
                ]
                selectedInits["start"] = pd.to_datetime(selectedInits["start"])
                selectedInits.sort_values(by=["start"], ascending=False, inplace=True)
                g = selectedInits.groupby(selectedInits["reqID"], sort=False)
                selectedInits = pd.concat(
                    islice(
                        map(itemgetter(1), g), max(0, g.ngroups - self.windowSize), None
                    )
                )
                # if (selectedInits.shape[0]) >= self.windowSize:
                #     selectedInits = selectedInits.head(self.windowSize)
                for _, record in selectedInits.iterrows():
                    durations.append(record["duration"])
                if mode == "best-case":
                    if host == "s":
                        exeTimes[func][mode] = self.getUpperBound(durations)
                    else:
                        exeTimes[func][mode] = self.getLowerBound(durations)

                elif mode == "worst-case":
                    if host == "s":
                        exeTimes[func][mode] = self.getLowerBound(durations)
                    else:
                        exeTimes[func][mode] = self.getUpperBound(durations)
                elif mode == "default":
                    exeTimes[func][mode] = self.getMean(durations)
        with open(
            (
                (os.path.dirname(os.path.abspath(__file__)))
                + "/data/"
                + str(self.workflow)
                + "/"
                + host
                + ", exeTime.json"
            ),
            "w",
            os.O_NONBLOCK,
        ) as outfile:
            json.dump(exeTimes, outfile)

    def getPrevDS(self, mode):
        prev_Json = self.prev_cost()
        if mode == "r":
            return prev_Json["DSread"]
        elif mode == "w":
            return prev_Json["DSwrite"]
        elif mode == "d":
            return prev_Json["DSdelete"]
        else:
            print("unknown mode!")

        prev_Json

    def getUnitCost_Datastore(self, mode):
        free_tier_read = 50000
        free_tier_write = 20000
        free_tier_delete = 20000
        unitRead = 0.06 / 100000
        unitWrite = 0.18 / 100000
        unitDelete = 0.02 / 100000
        prev = self.getPrevDS(mode)
        if mode == "r":
            if prev > free_tier_read:
                free_tier_read = 0
            else:
                free_tier_read = free_tier_read - prev
            cost = max(0, (1 - free_tier_read)) * unitRead
        elif mode == "w":
            if prev > free_tier_write:
                free_tier_write = 0
            else:
                free_tier_write = free_tier_write - prev
            cost = max(0, (1 - free_tier_write)) * unitWrite
        elif mode == "d":
            if prev > free_tier_delete:
                free_tier_delete = 0
            else:
                free_tier_delete = free_tier_delete - prev
            cost = max(0, (1 - free_tier_delete)) * unitDelete
        else:
            return "Unknown operation"
        return cost

    def cost_estimator_pubsub(self, bytes):
        free_tier_Bytes = 1024 * 1024 * 1024
        prev_Json = self.prev_cost()
        unit_price_TiB = 40

        if prev_Json["Bytes"] > free_tier_Bytes:
            free_tier_Bytes = 0
        else:
            free_tier_Bytes = free_tier_Bytes - prev_Json["Bytes"]
        calculatedbytes = max(
            0, ((max(1024, bytes) - free_tier_Bytes) / (1024 * 1024 * 1024 * 1024))
        )
        costB = calculatedbytes * unit_price_TiB
        return costB

    def getPubsubDF(self):
        # monitoringObj = monitoring()
        topicMsgSize = pd.read_pickle(
            (os.path.dirname(os.path.abspath(__file__))) + "/data/" + "topicMsgSize.pkl"
        )
        return topicMsgSize

    # func: function a message is published to (subscriber)
    def getPubSubCost(self, func):
        psSize = self.getPubSubSize(func)
        cost = self.cost_estimator_pubsub(psSize)
        return cost

    # func: function a message is published to (subscriber)
    def getPubSubSize(self, func):
        pubsubsizeDF = self.getPubsubDF()
        selectedtopic = self.topics[self.workflowFunctions.index(func)]
        psSize = pubsubsizeDF.loc[
            pubsubsizeDF["Topic"] == selectedtopic, "PubsubMsgSize"
        ].item()
        return psSize

    def getPubSubMessageSize(self):
        pubSubSize = {}
        pubsubsizeDF = self.getPubsubDF()
        for func in self.workflowFunctions:
            if func != self.initFunc:
                selectedtopic = self.topics[self.workflowFunctions.index(func)]
                psSizeSeries = pubsubsizeDF.loc[
                    pubsubsizeDF["Topic"] == selectedtopic, "PubsubMsgSize"
                ]
                if len(psSizeSeries) == 0:
                    pubSubSize[func] = 0
                else:
                    psSize = psSizeSeries.item()
                    pubSubSize[func] = psSize
        nonzero_vals = [
            pubSubSize[func] for func in pubSubSize.keys() if pubSubSize[func] != 0
        ]
        if len(nonzero_vals) != 0:
            average_nonzeroes = np.mean(np.array(nonzero_vals))
            for func in pubSubSize.keys():
                if pubSubSize[func] == 0:
                    pubSubSize[func] = average_nonzeroes
        else:
            print("No prior data on pub/sub message size yet!")
        with open(
            (
                (os.path.dirname(os.path.abspath(__file__)))
                + "/data/"
                + str(self.workflow)
                + "/"
                + "pubSubSize.json"
            ),
            "w",
            os.O_NONBLOCK,
        ) as outfile:
            json.dump(pubSubSize, outfile)

    def getComCost(self, msgSize):
        cost = self.cost_estimator_pubsub(msgSize)
        return cost

    def getFuncExecutionTime(self, func, host, mode):
        exeTime = 0
        durations = []
        selectedInits = self.dataframe.loc[
            (self.dataframe["function"] == func) & (self.dataframe["host"] == host)
        ]
        selectedInits["start"] = pd.to_datetime(selectedInits["start"])
        selectedInits.sort_values(by=["start"], ascending=False, inplace=True)
        if (len(selectedInits) == 0) and (len(durations) == 0):
            return 0
        if len(selectedInits) != 0:
            g = selectedInits.groupby(selectedInits["reqID"], sort=False)
            selectedInits = pd.concat(
                islice(map(itemgetter(1), g), max(0, g.ngroups - self.windowSize), None)
            )
            # if (selectedInits.shape[0]) >= self.windowSize:
            #     selectedInits = selectedInits.head(self.windowSize)
            for _, record in selectedInits.iterrows():
                durations.append(record["duration"])
        if mode == "best-case":
            if host == "s":
                exeTime = self.getUpperBound(durations)
            else:
                exeTime = self.getLowerBound(durations)

        elif mode == "worst-case":
            if host == "s":
                exeTime = self.getLowerBound(durations)
            else:
                exeTime = self.getUpperBound(durations)
        elif mode == "default":
            exeTime = self.getMean(durations)
        return exeTime

    def get_num_per_req(self, func, test):
        if test is True:
            return 1
        selectedInits = self.dataframe.loc[(self.dataframe["function"] == func)]
        counts = (selectedInits.groupby(["reqID"]).size().reset_index(name="counts"))[
            "counts"
        ].to_numpy()
        numPerReq = self.getMean(counts)
        return numPerReq

    # Check Here!!!!
    def getComLatency(self, child, parent, childHost, parentHost, mode):
        if childHost != "s":
            childHost = "vm" + str(childHost)
        if parentHost != "s":
            parentHost = "vm" + str(parentHost)
        selectedInitsParent = self.dataframe.loc[
            (self.dataframe["function"] == parent)
            & (self.dataframe["host"] == parentHost)
        ]
        if len(self.predecessors[self.workflowFunctions.index(child)]) > 1:
            selectedInitsChild = self.dataframe.loc[
                (self.dataframe["function"] == child)
                & (self.dataframe["host"] == childHost)
                & (self.dataframe["mergingPoint"] == parent)
            ]
        else:
            selectedInitsChild = self.dataframe.loc[
                (self.dataframe["function"] == child)
                & (self.dataframe["host"] == childHost)
            ]
        gatheredDF = pd.concat([selectedInitsParent, selectedInitsChild])
        dfByReq = gatheredDF.groupby(["reqID"])
        dSet = (((dfByReq["function"].agg(lambda x: len(set(x)))))).to_frame()
        dSet = ((dSet.loc[(dSet["function"] == 2)])).to_dict()
        reqs = list(dSet["function"].keys())
        if len(reqs) >= self.windowSize:
            reqs = reqs[: self.windowSize]
        if len(reqs) == 0:
            # print(
            #     "NOTFOUND:::", parent, "::", parentHost, "-->", child, ":::", childHost
            # )
            return "NotFound"
        selectedInitsParentFinish = (
            selectedInitsParent[(selectedInitsParent.reqID.isin(reqs))]
        )[["reqID", "finish"]]
        selectedInitsParentFinish["finish"] = pd.to_datetime(
            selectedInitsParentFinish["finish"]
        )
        selectedInitsParentFinish = (
            (
                selectedInitsParentFinish[
                    selectedInitsParentFinish.groupby("reqID").finish.transform("max")
                    == selectedInitsParentFinish["finish"]
                ]
            )
            .set_index("reqID")
            .to_dict()["finish"]
        )
        # if len(self.predecessors[self.workflowFunctions.index(parent)]) > 1:
        #     selectedInitsParentFinish = (
        #         selectedInitsParent[(selectedInitsParent.reqID.isin(reqs))]
        #     )[["reqID", "finish"]]
        #     selectedInitsParentFinish["finish"] = pd.to_datetime(
        #         selectedInitsParentFinish["finish"]
        #     )
        #     selectedInitsParentFinish = (
        #         (
        #             selectedInitsParentFinish[
        #                 selectedInitsParentFinish.groupby("reqID").finish.transform(
        #                     "max"
        #                 )
        #                 == selectedInitsParentFinish["finish"]
        #             ]
        #         )
        #         .set_index("reqID")
        #         .to_dict()["finish"]
        #     )
        # else:
        #     # selectedInitsParentFinish = (
        #     #     (selectedInitsParent[(selectedInitsParent.reqID.isin(reqs))])[
        #     #         ["reqID", "finish"]
        #     #     ]
        #     #     .set_index("reqID")
        #     #     .to_dict()["finish"]
        #     # )
        #     selectedInitsParentFinish = (selectedInitsParent[selectedInitsParent.reqID.isin(reqs)])[
        #                         ["reqID", "finish"]
        #                     ]
        #     selectedInitsParentFinish = (selectedInitsParentFinish.groupby(['reqID'])['finish'].max()).to_frame()
        #     selectedInitsParentFinish = selectedInitsParentFinish.to_dict()["finish"]

        # newMergingPatternChanges
        if len(self.predecessors[self.workflowFunctions.index(child)]) > 1:
            selectedInitsChildStart = (
                (
                    selectedInitsChild[
                        (selectedInitsChild.reqID.isin(reqs))
                        & (selectedInitsChild.mergingPoint == parent)
                    ]
                )[["reqID", "start"]]
                .set_index("reqID")
                .to_dict()["start"]
            )
        else:
            # selectedInitsChildStart = (
            #     (selectedInitsChild[selectedInitsChild.reqID.isin(reqs)])[
            #         ["reqID", "start"]
            #     ]
            #     .set_index("reqID")
            #     .to_dict()["start"]
            # )
            # selectedInitsChildStart = (selectedInitsChild[selectedInitsChild.reqID.isin(reqs)])[
            #                     ["reqID", "start"]
            #                 ]
            # selectedInitsChildStart = (selectedInitsChildStart.groupby(['reqID'])['start'].min()).to_frame()
            # selectedInitsChildStart = selectedInitsChildStart.to_dict()["start"]
            selectedInitsChildStart = (
                selectedInitsChild[(selectedInitsChild.reqID.isin(reqs))]
            )[["reqID", "start"]]
            selectedInitsChildStart["start"] = pd.to_datetime(
                selectedInitsChildStart["start"]
            )
            selectedInitsChildStart = (
                (
                    selectedInitsChildStart[
                        selectedInitsChildStart.groupby("reqID").start.transform("min")
                        == selectedInitsChildStart["start"]
                    ]
                )
                .set_index("reqID")
                .to_dict()["start"]
            )
        newDF = pd.DataFrame(
            {
                "start": pd.Series(selectedInitsChildStart),
                "end": pd.Series(selectedInitsParentFinish),
            }
        )
        newDF["start"] = newDF["start"].apply(
            lambda x: (datetime.datetime.strptime(x, "%Y-%m-%d %H:%M:%S.%f")).replace(
                tzinfo=None
            )
            if type(x) == str
            else x.replace(tzinfo=None)
        )
        newDF["end"] = newDF["end"].apply(
            lambda x: (datetime.datetime.strptime(x, "%Y-%m-%d %H:%M:%S.%f")).replace(
                tzinfo=None
            )
            if type(x) == str
            else x.replace(tzinfo=None)
        )
        newDF["duration"] = (
            (newDF["start"] - newDF["end"]).dt.total_seconds().mul(1000).astype(int)
        )
        # print(newDF)
        durations = newDF["duration"].tolist()
        if mode == "best-case":
            exeTime = self.getLowerBound(durations)
        elif mode == "worst-case":
            exeTime = self.getUpperBound(durations)
        elif mode == "default":
            exeTime = self.getMean(durations)
        serverlessDuration = self.slackDurationsDF[parent + "-" + child][mode]
        # print("\\\\////\\\\\DIFF:::", (exeTime - serverlessDuration),":::", parent,"-",parentHost
        # , "----", child,"-",childHost
        # )
        return exeTime - serverlessDuration

    def getCost(self):
        costs = {}
        decisionModes = (self.rankerConfig["decisionMode"]).split()
        for func in self.workflowFunctions:
            costs[func] = {}
        for mode in decisionModes:
            for func in self.workflowFunctions:
                GB = self.memories[self.workflowFunctions.index(func)]
                durations = []
                selectedInits = self.dataframe.loc[
                    (self.dataframe["function"] == func)
                    & (self.dataframe["host"] == "s")
                ]
                selectedInits["start"] = pd.to_datetime(selectedInits["start"])
                selectedInits.sort_values(by=["start"], ascending=False, inplace=True)
                g = selectedInits.groupby(selectedInits["reqID"], sort=False)
                selectedInits = pd.concat(
                    islice(
                        map(itemgetter(1), g), max(0, g.ngroups - self.windowSize), None
                    )
                )
                # if (selectedInits.shape[0]) >= self.windowSize:
                #     selectedInits = selectedInits.head(self.windowSize)
                for _, record in selectedInits.iterrows():
                    durations.append(record["duration"])
                if mode == "best-case":
                    et = self.getUpperBound(durations)
                    costs[func][mode] = self.cost_estimator(1, et, GB)

                elif mode == "worst-case":
                    et = self.getLowerBound(durations)
                    costs[func][mode] = self.cost_estimator(1, et, GB)
                elif mode == "default":
                    et = self.getMean(durations)
                    costs[func][mode] = self.cost_estimator(1, et, GB)
        with open(
            (
                (os.path.dirname(os.path.abspath(__file__)))
                + "/data/"
                + str(self.workflow)
                + "/"
                + "Costs.json"
            ),
            "w",
            os.O_NONBLOCK,
        ) as outfile:
            json.dump(costs, outfile)

    def getFuncCost(self, mode, func):

        GB = self.memories[self.workflowFunctions.index(func)]
        durations = []
        selectedInits = self.dataframe.loc[
            (self.dataframe["function"] == func) & (self.dataframe["host"] == "s")
        ]
        selectedInits["start"] = pd.to_datetime(selectedInits["start"])
        selectedInits.sort_values(by=["start"], ascending=False, inplace=True)
        g = selectedInits.groupby(selectedInits["reqID"], sort=False)
        selectedInits = pd.concat(
            islice(map(itemgetter(1), g), max(0, g.ngroups - self.windowSize), None)
        )
        # if (selectedInits.shape[0]) >= self.windowSize:
        #     selectedInits = selectedInits.head(self.windowSize)
        for _, record in selectedInits.iterrows():
            durations.append(record["duration"])
        if mode == "best-case":
            et = self.getUpperBound(durations)
            cost = self.cost_estimator(1, et, GB)

        elif mode == "worst-case":
            et = self.getLowerBound(durations)
            cost = self.cost_estimator(1, et, GB)
        elif mode == "default":
            et = self.getMean(durations)
            cost = self.cost_estimator(1, et, GB)
        return cost

    def getDurationsList(self, func, host):
        durations = []
        selectedInits = self.dataframe.loc[
            (self.dataframe["function"] == func) & (self.dataframe["host"] == host)
        ]
        selectedInits["start"] = pd.to_datetime(selectedInits["start"])
        selectedInits.sort_values(by=["start"], ascending=False, inplace=True)
        if (len(selectedInits) == 0) and (len(durations) == 0):
            print("No records found for {} running in {}".format(func, host))
            return []
        if len(selectedInits) != 0:
            g = selectedInits.groupby(selectedInits["reqID"], sort=False)
            selectedInits = pd.concat(
                islice(map(itemgetter(1), g), max(0, g.ngroups - self.windowSize), None)
            )
            for _, record in selectedInits.iterrows():
                durations.append(record["duration"])
        return durations

    def distributions_SMDTest(self, vmDurations, serverlessDuration):
        print("SMD")
        vmMean = np.mean(np.array(vmDurations))
        serverlessMean = np.mean(np.array(serverlessDuration))
        vmStd = np.std(np.array(vmDurations))
        serverlessStd = np.std(np.array(serverlessDuration))
        SMD = abs(vmMean - serverlessMean) / math.sqrt(
            ((vmStd ** 2) + (serverlessStd ** 2)) / 2
        )
        print("SMD::", SMD)
        if SMD < 0.1:
            # the distributions are similar in that case
            return 1
        else:
            return 0

    def distributions_KS_Test(self, vmDurations, serverlessDuration):
        print("KS_Test")
        ksTestRes = ks_2samp(vmDurations, serverlessDuration)
        pvalue = ksTestRes.pvalue
        print(pvalue)
        if pvalue < 0.05:
            # reject null hypothesis, so different distributions
            return 0
        else:
            return 1

    def distributions_Mann_Whitney_Test(self, vmDurations, serverlessDuration):
        print("Mann_Whitney_Test")
        stat, pvalue = mannwhitneyu(vmDurations, serverlessDuration)
        # 1: in case the distributions are similar,
        # 0: in case the distributions are different
        print(pvalue)
        if pvalue < 0.05:
            # reject null hypothesis, so different distributions
            return 0
        else:
            return 1

    def distributions_Chisquared_Test(self, vmDurations, serverlessDuration):
        print("Chisquared_Test")
        binsDF = pd.DataFrame()
        # Generate bins from control group
        _, bins = pd.qcut(serverlessDuration, q=10, retbins=True)
        binsDF["bin"] = pd.cut(serverlessDuration, bins=bins).value_counts().index

        # Apply bins to both groups
        binsDF["duration_c_observed"] = (
            pd.cut(serverlessDuration, bins=bins).value_counts().values
        )
        binsDF["duration_t_observed"] = (
            pd.cut(vmDurations, bins=bins).value_counts().values
        )

        # Compute expected frequency in the treatment group
        binsDF["duration_t_expected"] = (
            binsDF["duration_c_observed"]
            / np.sum(binsDF["duration_c_observed"])
            * np.sum(binsDF["duration_t_observed"])
        )
        stat, pvalue = chisquare(
            binsDF["duration_t_observed"], binsDF["duration_t_expected"]
        )
        print(pvalue)
        if pvalue < 0.05:
            # reject null hypothesis, so different distributions
            return 0
        else:
            return 1

    def compareDistributions(self, func, vmNum):
        # 1: in case the distributions are similar,
        # 0: in case the distributions are different

        vmDurations = self.getDurationsList(func, "vm" + str(vmNum))
        serverlessDuration = self.getDurationsList(func, "s")
        if len(vmDurations) == 0:
            # we don't have data on vm executions
            return "NotFound"
        # res = self.distributions_SMDTest(vmDurations, serverlessDuration)
        res = self.distributions_KS_Test(vmDurations, serverlessDuration)
        # res = self.distributions_Mann_Whitney_Test(vmDurations, serverlessDuration)
        # res = self.distributions_Chisquared_Test(vmDurations, serverlessDuration)
        return res

    def tripleCaseDecision(self, totalVMs):
        thresholdParam = 0.3
        individualDecisions = []
        for vmNum in range(totalVMs):
            for func in self.workflowFunctions:
                separateDecision = self.compareDistributions(func, vmNum)
                if separateDecision != "NotFound":
                    individualDecisions.append(separateDecision)
        print("individualDecisions, ", individualDecisions)
        if len(individualDecisions) == 0:
            return False
        elif np.sum(individualDecisions) >= thresholdParam * len(individualDecisions):
            # The distributions are similar, so run the solver in three cases
            return True
        else:
            return False


if __name__ == "__main__":
    workflow = "Text2SpeechCensoringWorkflow"
    # workflow = "TestCaseWorkflow"
    x = Estimator(workflow)
    x.getCost()
    # x.getExecutionTime("s")
    x.getPubSubMessageSize()
    # x.getExecutionTime("vm0")
    # print(x.getFuncExecutionTime("D", "vm0", "worst-case"))
