import requests
from urllib.parse import urljoin
import json
import os
from objectifier import Objectifier
import logging
import release_templates

config= json.loads(os.environ.get('config'))
config=Objectifier(config)

AHA_TOKEN=config.AHA_TOKEN
ZENHUB_TOKEN=config.ZENHUB_TOKEN
AHA_HEADER={'Authorization':AHA_TOKEN,'Content-Type': "application/json","User-Agent":"praveentechnic@gmail.com"}
ZENHUB_HEADER={'X-Authentication-Token':ZENHUB_TOKEN}
GITHUB_TOKEN=config.GITHUB_TOKEN

logging.basicConfig(level=logging.INFO,
 format="%(levelname)s:%(filename)s,%(lineno)d:%(name)s.%(funcName)s:%(message)s", 
  handlers=[logging.StreamHandler()])
logger=logging.getLogger()



#Get all the releases from Zenhub

def getReleasesFromZenhub(repoid):
    url=urljoin(config.Zenhub_Domain,'/p1/repositories/{0}/reports/releases'.format(str(repoid)))
    rs= requests.get(url=url, headers=ZENHUB_HEADER)
    if(rs.status_code==200):
        return rs.json()
    else:
        return None

#Get All Releases from Aha!

def getReleasesfromAha(page=1):
    data={"releases":[]}
    url=urljoin(config.Aha_Domain,'/api/v1/products/{product_id}/releases'.format(product_id=config.product_id))
    rs= requests.get(url, headers=AHA_HEADER,params={"page":page})
    if(rs.status_code==200):
        data["releases"]=data["releases"]+rs.json()['releases']
        currentpage=rs.json()['pagination']['current_page']
        total_pages=rs.json()['pagination']['total_pages']
        if(total_pages!=currentpage):
            data["releases"]=data["releases"]+getReleasesfromAha(page=currentpage+1)['releases']
    else:
        return None
    return data

#Create a Release on Aha!
def createReleaseOnAha( name , release_date, workflow_status,owner="aarthi.videep@qubecinema.com" ):
    url=urljoin(config.Aha_Domain,'/api/v1/products/{product_id}/releases'.format(product_id=config.product_id))
    data={
        "release":{
            "owner":owner,
            "name":name,
            "release_date":release_date,
            "workflow_status":workflow_status
        }
    }
    rs=requests.post(url=url, json=data, headers= AHA_HEADER)
    if(rs.status_code==200):
        return rs.json()
    else:
        return {'state':'FAILED', 'status_code': rs.status_code , 'response':rs.text()}


#Udpate a Release on Aha!

def updateReleaseOnAha(id, name, release_date, workflow_status):
    url=urljoin(config.Aha_Domain,'/api/v1/products/{product_id}/releases/{id}'.format(product_id=config.product_id, id= id))
    data={
        "release":{            
            
        }
    }
    if(name is not None):
        data['release']['name']=name
    if(release_date is not None):
        data['release']['release_date']=release_date
    if(workflow_status is not None):
        data['release']['workflow_status']=workflow_status

    rs=requests.put(url, json=data, headers=AHA_HEADER)
    if(rs.status_code==200):
        return rs.json()
    else:
        return {'state':'FAILED', 'status_code': rs.status_code , 'response':rs.text()}

#generatediff
def generatediff(ZH_Release, Aha_Release):
    changes={"name":None, "release_date":None, "workflow_status":None }
    if(ZH_Release['title'] != Aha_Release['release']['name']):
        changes['name']=ZH_Release['title']
    if(ZH_Release['desired_end_date'].split('T')[0] != Aha_Release['release']['release_date'] ):
        changes['release_date']=ZH_Release['desired_end_date'].split('T')[0]
    status=ZH_Release['state']
    if(status=='open'):
        status='Backlog'
    if(status=='closed'):
        status='Released'
    if(status!=Aha_Release['release']['workflow_status']['name']):
        changes['workflow_status']=status

    return changes

def getAhaReleasebyId(id):
    url=urljoin(config.Aha_Domain,'/api/v1/releases/{0}'.format(id))
    rs=requests.get(url=url, headers=AHA_HEADER)
    if(rs.status_code==200):
        return rs.json()
    else:
        return None

def getZHReleasebyID(AllReleases, id):
    for items in AllReleases:
        if(items['release_id']==id):
            return items
    return None

#Get Translation data
def getTranslationData(jsoncontent,key):
    try:
        return jsoncontent[key]
    except KeyError:
        logging.error("The requested translation data {0} is not found on the map".format(key))
        return None

def create_release_phase(data):
    url=urljoin(config.Aha_Domain,'/api/v1/release_phases')
    rs= requests.post(url, headers=AHA_HEADER , json = data)
    if(rs.status_code==200):
        logger.info("Created Release phase ")
        return rs.json()
    else:
        return None

#Add Release Templates to the Created releases
def add_Release_Templates(response):
    ID = response['release']['id']
    start_date = response['release']['start_date']
    end_date = response['release']['release_date']
    template = release_templates.get_release_templates(ID,start_date,end_date)
    for items in template:
        create_release_phase(items)



def main():
    endurance=requests.get(config.Endurance_Source_3, headers={'x-api-key':config.ndurance_key}).json()
    if(endurance is None):
        raise Exception
    else:
        pass
    
    Releases_in_Zenhub=getReleasesFromZenhub(config.Zenhub_repo_Id)
    Releases_in_Aha = getReleasesfromAha()
    
    try:
        for release in Releases_in_Zenhub:
            if(getTranslationData(endurance,release['release_id']) is None and release['title'] not in json.dumps(Releases_in_Aha) ): #Data is not available in endurance, So we are creating a new release , 2 Level Check 
                release_date_to_be_updated_to_AHA= release['desired_end_date'].split('T')[0]
                status=release['state']
                if(status=='open'):
                    status='Backlog'
                if(status=='closed'):
                    status='Released'
                creation=createReleaseOnAha(name=release['title'], release_date = release_date_to_be_updated_to_AHA, workflow_status=status)
                if('state' not in creation.keys()):
                    add_Release_Templates(creation)
                    logger.info("Created new Release on Aha! {0}".format(creation['release']['reference_num']))
                    endurance[release['release_id']]={"aha_ref_num":creation['release']['reference_num'], "aha_release_id": creation['release']['id']}
                else:
                    logger.error("Error while Creating Release on Aha! : {0}".format(str(creation)))
                
            else:# data is available, so we will check for updates
                aha_releaseId=endurance[release['release_id']]['aha_release_id']

                single_Aha_Release= getAhaReleasebyId(aha_releaseId)
                single_ZH_Release= getZHReleasebyID(Releases_in_Zenhub, release['release_id'])
                diff= generatediff(single_ZH_Release, single_Aha_Release)
                if(diff != {"name":None, "release_date":None , "workflow_status":None}):
                    updation= updateReleaseOnAha(id=aha_releaseId, name= diff['name'], release_date= diff['release_date'] , workflow_status= diff['workflow_status'])                                

                    if('state' not in updation.keys()):
                        logger.info("Updated Release On Aha {0}".format(str(updation)))
                    else:
                        logger.error("Error while updating a release on Aha : {0}".format(str(updation)))
    except Exception as e:
        print(str(e))
    finally:
        requests.post(config.Endurance_Source_3, headers={'x-api-key':config.ndurance_key}, json= endurance)




