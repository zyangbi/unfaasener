from google.cloud import functions_v1
import os
from pathlib import Path
import subprocess
import sys
import wget
from zipfile import ZipFile
import configparser

configPath = (
    str(Path(os.path.dirname(os.path.abspath(__file__))).resolve().parents[1])
    + "/project-config.ini"
)
globalConfig = configparser.ConfigParser()
globalConfig.read(configPath)
projectConfig = globalConfig["settings"]
project_id = str(projectConfig["projectid"])

subscription_id = sys.argv[1]
# timeout = 22.0
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
    str(Path(os.path.dirname(os.path.abspath(__file__)))) + "/vmExeModule.json"
)


def containerize(functionname):
    # Create a client
    client = functions_v1.CloudFunctionsServiceClient()

    # Initialize request arguments
    request = functions_v1.GenerateDownloadUrlRequest(
        name="projects/"
        + project_id
        + "/locations/northamerica-northeast1/functions/"
        + functionname,
    )

    # Make the request
    response = client.generate_download_url(request=request)
    downloadlink = str(response).split(" ")[1].split('"')[1]

    # Download the function
    # print("\nDownloading the function")
    wget.download(downloadlink, functionname + ".zip")
    request = functions_v1.GetFunctionRequest(
        name="projects/"
        + project_id
        + "/locations/northamerica-northeast1/functions/"
        + functionname,
    )

    # Make the request
    response = client.get_function(request=request)
    entrypoint = response.entry_point

    # Unzip the function
    # print("\nUnzipping the function")
    with ZipFile(functionname + ".zip", "r") as zipObj:
        zipObj.extractall(functionname)
    with open(
        str(Path(os.path.dirname(os.path.abspath(__file__)))) + "/output2.log", "a"
    ) as output:
        # print("\nCreating the Docker container \n")
        # Copy the Docker file to the unzipped folder
        subprocess.call(
            "cp Dockerfile " + functionname, shell=True, stdout=output, stderr=output
        )
        subprocess.call(
            "cp init.sh " + functionname, shell=True, stdout=output, stderr=output
        )
        file_object = open(functionname + "/main.py", "a")
        file_object.write("\nimport sys\n")
        file_object.write("def main():\n")
        file_object.write(
            "    " + entrypoint + "(json.loads(sys.argv[1]),sys.argv[2])\n"
        )
        file_object.write("if __name__ == '__main__':\n")
        file_object.write("    main()\n")
        file_object.close()
        subprocess.call(
            "cp vmExeModule.json " + functionname + "/ ",
            shell=True,
            stdout=output,
            stderr=output,
        )
        subprocess.call(
            "sed -i 's/json.loads(base64.b64decode//g' " + functionname + "/main.py ",
            shell=True,
            stdout=output,
            stderr=output,
        )
        subprocess.call(
            "sed -i \"s/.decode('utf-8'))//g\" " + functionname + "/main.py ",
            shell=True,
            stdout=output,
            stderr=output,
        )
        # Create the image from the Dockerfile also copy the function's code
        subprocess.call(
            "cd "
            + functionname
            + "; docker build . < Dockerfile --tag name:"
            + functionname,
            shell=True,
            stdout=output,
            stderr=output,
        )
    # subprocess.call("cd .. ")
    # subprocess.call("rm -rf "+ functionname)
    # subprocess.call("rm -rf "+ functionname+".zip")


def run_container(functionname):
    with open("/tmp/output.log", "a") as output:
        print("\nRunning the Docker container \n")
        subprocess.call(
            "docker run name:" + functionname, shell=True, stdout=output, stderr=output
        )


def main():
    containerize(sys.argv[1])


#    run_container(sys.argv[1])

if __name__ == "__main__":
    main()
