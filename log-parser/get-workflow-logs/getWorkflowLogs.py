from getNewServerlessLogs import getNewLogs
from getNewDatastoreLogs import dataStoreLogParser
import time
from pathlib import Path
import os
import sys
import logging
import datetime
import configparser


logging.basicConfig(
    filename=str(Path(os.path.dirname(os.path.abspath(__file__))))
    + "/logs/logParser.log",
    level=logging.INFO,
)
sys.path.append(
    str(Path(os.path.dirname(os.path.abspath(__file__))).resolve().parents[1])
    + "/scheduler"
)
from baselineSlackAnalysis import baselineSlackAnalysisClass
from monitoring import monitoring


class getWorkflowLogs:
    def __init__(self, workflow):
        serverless = getNewLogs(workflow)
        # vm = dataStoreLogParser(workflow)


if __name__ == "__main__":
    interruptTime = 60
    initial = int(sys.argv[2])
    path = (
        str(Path(os.path.dirname(os.path.abspath(__file__))).resolve().parents[1])
        + "/scheduler/rankerConfig.ini"
    )
    config = configparser.ConfigParser()
    config.read(path)
    rankerConfig = config["settings"]
    mode = rankerConfig["mode"]
    if initial == 1:
        start_time = time.time()
        # workflow = "Text2SpeechCensoringWorkflow"
        workflow = sys.argv[1]
        x = getWorkflowLogs(workflow)
        if mode == "latency":
            baselineSlackAnalysisObj = baselineSlackAnalysisClass(workflow)
            # rankerConfig["tolerancewindow"] = str(2* (baselineSlackAnalysis.getCriticalPathDuration()))
        monitoringObj = monitoring()
        print("--- %s seconds ---" % (time.time() - start_time))
    else:
        print("---------getting new logs:---------------")
        time.sleep(interruptTime)
        while True:
            start_time = time.time()
            workflow = sys.argv[1]
            # workflow = "Text2SpeechCensoringWorkflow"
            logging.info("periodic log parser is running......")
            logging.info(str(datetime.datetime.now()))
            x = getWorkflowLogs(workflow)
            if mode == "latency":
                baselineSlackAnalysisObj = baselineSlackAnalysisClass(workflow)
                # rankerConfig["tolerancewindow"] = str(2* (baselineSlackAnalysis.getCriticalPathDuration()))
            monitoringObj = monitoring()
            print("--- %s seconds ---" % (time.time() - start_time))
            timeSpent = "time spent: " + str((time.time() - start_time))
            logging.info(timeSpent)
            time.sleep(interruptTime)
