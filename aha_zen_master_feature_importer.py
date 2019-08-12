import requests
#import config
import os
import json
from objectifier import Objectifier
import github3
from autologging import logged,traced,TRACE 
import logging
import sys
from datetime import datetime
config= json.loads(os.environ.get('config'))
config=Objectifier(config)
from urllib.parse import urljoin
import time
import releases


logging.basicConfig(level=logging.INFO,
 format="%(levelname)s:%(filename)s,%(lineno)d:%(name)s.%(funcName)s:%(message)s", 
  handlers=[logging.StreamHandler()])
logger=logging.getLogger()



AHA_TOKEN=config.AHA_TOKEN
ZENHUB_TOKEN=config.ZENHUB_TOKEN
GITHUB_TOKEN=config.GITHUB_TOKEN
RELEASES_AHA=None



AHA_HEADER={'Authorization':AHA_TOKEN,'Content-Type': "application/json","User-Agent":"praveentechnic@gmail.com"}
ZENHUB_HEADER={'X-Authentication-Token':ZENHUB_TOKEN}
ZH_ISSUE_RELEASE_MAP={}



########################DATA_STORE##################################
ENDURANCE= requests.get(config.Endurance_Source, headers={'x-api-key':config.ndurance_key}).json()
ENDURANCE_RELEASES= requests.get(config.Endurance_Source_3, headers={'x-api-key':config.ndurance_key}).json()
############################################################

def get_issues_under_releaseID_ZH(release_id):
    rs= requests.get(urljoin(config.Zenhub_Domain,'/p1/reports/release/{0}/issues'.format(str(release_id))), headers = ZENHUB_HEADER)
    if(rs.status_code==200):
        return rs.json()
    else:
        return None


def build_Release_Map_ZH():
    #Get All  Releases on ZH
    ZH_Releases= releases.getReleasesFromZenhub(config.Zenhub_repo_Id)
    Issue_Release_Map={}
    for rl in ZH_Releases:
        issues=get_issues_under_releaseID_ZH(rl['release_id'])
        for issue in issues:
            if(str(issue['repo_id'])==config.Zenhub_repo_Id):
                Issue_Release_Map[str(issue['issue_number'])]=rl['release_id']
    return Issue_Release_Map



#Get list of Epics from Zen hub
def getListOfEpicsZen():
    rs=requests.get(url= urljoin(config.Zenhub_Domain,'/p1/repositories/{0}/epics'.format(config.Zenhub_repo_Id)),headers=ZENHUB_HEADER)
    if(rs.status_code==200):
        return rs.json()
    else:
        logger.error("Failure While Fetching details from Zenhub"+ str(rs.status_code)+ str(rs.content))
        return None

#Get Translation data - handle key errors internally
def getTranslationData(jsoncontent,key):
    try:
        return jsoncontent[key]
    except Exception:
        
        return None

#create an instance of github_object and return the same
def github_object(TOKEN,repository):
    repository=repository
    gh = github3.GitHub(token=TOKEN)
    owner,name=repository.split('/',1)
    repo= gh.repository(owner,name)
    return repo

#Get Details of an issue from Zenhub
def getIssueDetailFromZen(repoid,issue_id):
    rs= requests.get(url= urljoin(config.Zenhub_Domain,'/p1/repositories/{0}/issues/{1}'.format(str(repoid),str(issue_id))),headers=ZENHUB_HEADER)
    if(rs.status_code==200):
        result= rs.json()
        result['id']=issue_id
        return result
    else:
        #Log error
        return None

# Get list of available release milestones from Aha
def getAllReleasesfromAha():
    current_page=1
    totalpage=10
    releases={}
    while current_page<=totalpage:
        time.sleep(.25)
        rs=requests.get(url= urljoin(config.Aha_Domain,'/api/v1/products/{0}/releases'.format(config.product_ref)),params={'page':current_page},headers=AHA_HEADER)
        if(rs.status_code==200):
            data=rs.json()
            for items in data['releases']:
                releases[items['name']]=items
            totalpage=data['pagination']['total_pages']
            current_page=current_page+1
        elif(rs.status_code==429):
            logger.error('hit Rate Limit while getting release details. Sleeping 10 secs')
            time.sleep(10)
        else:
            logger.error('Non 200 status code while getting release details from Aha')
            break
    return releases

def getEpicDataGit():
    pass

#Get all the master features from Aha
def getMasterFeatureAha():
    rs=requests.get(url=  urljoin(config.Aha_Domain,'api/v1/master_features'), headers=AHA_HEADER)
    if(rs.status_code==200):
        return rs.json()
    else:
        logger.error('Non 200 status code while getting master feature from Aha! --> {0}'.format(rs.status_code))
        return None

#Create a new master feature on Aha
def insertMasterFeatureAha(release_id,NAME,DESC,STATUS="Under consideration", due_date=None):    
    model={
  "master_feature": {
    "name": NAME,
    "description": DESC,    
    "workflow_status": {            
            "name": STATUS
        }
            }
            }
    if(release_id != None and config.update_release_dates):
        for items in RELEASES_AHA:
            if(RELEASES_AHA[items]['id']==release_id):
                model['master_feature']['start_date']=RELEASES_AHA[items]['start_date']
                model['master_feature']['due_date']=RELEASES_AHA[items]['release_date']
        rs=requests.post(url= urljoin(config.Aha_Domain ,'api/v1/releases/{release_id}/master_features'.format(release_id=release_id)),data=json.dumps(model), headers=AHA_HEADER)
        return rs

    if(due_date!=None):
        model['master_feature']['due_date']=due_date
   
    rs=requests.post(url= urljoin(config.Aha_Domain,'api/v1/products/{0}/master_features'.format(config.product_id)),data=json.dumps(model),headers=AHA_HEADER)
    return rs


#Update the Master feature on Aha
def updateMasterFeatureAha(id,changes={}):
    model={
  "master_feature": {}
    }
    for items in changes:
        model['master_feature'][items]=changes[items]
    rs=requests.put(url= urljoin(config.Aha_Domain,'api/v1/master_features/{0}'.format(id)), data=json.dumps(model), headers=AHA_HEADER)
    return rs

#Get details about the master feature on Aha
def getMasterFeatureDetailAha(id):
    rs=requests.get( url= urljoin( config.Aha_Domain,'api/v1/master_features/{0}'.format(id)), headers=AHA_HEADER)
    if(rs.status_code==200):
        return rs.json()
    else:
        #TODO: Log Failure Error for incorrect response
        return None

#Main workflow
def main():
    final_Changes=[]
    Aha_releases= getAllReleasesfromAha()
    global RELEASES_AHA
    RELEASES_AHA=Aha_releases
    Zen_Epics=getListOfEpicsZen()
    git_repo=github_object(GITHUB_TOKEN,config.repo_name)
    global ZH_ISSUE_RELEASE_MAP
    ZH_ISSUE_RELEASE_MAP=build_Release_Map_ZH()

    for items in Zen_Epics['epic_issues']:
        #check if item is available in Endurance:
        logger.info('processing: '+str(items))
        aha_epic=getTranslationData(ENDURANCE,str(items['issue_number']))
        if(aha_epic==None):
            issue=git_repo.issue(items['issue_number'])
            try:
                if(config.update_release_dates):
                    release_id=Aha_releases[issue.milestone.title]['reference_num'] if issue.milestone is not None else None
                else:
                    release_id=None                    
            except:
                release_id=None
            if(config.Track_due_date and issue.milestone is not None):
                due_date=str(issue.milestone.due_on.date())
            else:
                due_date=None
            zen_issue_detail=getIssueDetailFromZen(repoid=config.Zenhub_repo_Id,issue_id=items['issue_number'])
            name=issue.title
            description=issue.body
            try:
                status=getTranslationData(json.load(open('zen2ahaMap.json')),zen_issue_detail['pipeline']['name'])            
            except:
                status=None
            if(status is not None):
                response=insertMasterFeatureAha(release_id,name,description,status, due_date=due_date)
                if(response.status_code==200):
                    this_master_feature=response.json()
                    logger.info("CREATED"+  str(this_master_feature['master_feature']['reference_num']))
                    ENDURANCE[str(items['issue_number'])]={
                        "aha_ref_num":this_master_feature['master_feature']['reference_num']
                    }
                else:
                    #TODO log Error Failure
                    logger.info(response.status_code)
            else:
                #TODO Log error for status not available
                print(' status un available')
                pass
        else:
            #TODO Logic for updating the Master feature
            #Update the folllowing> name, description, status, release id
            issue=git_repo.issue(items['issue_number'])
            zen_issue_detail=getIssueDetailFromZen(repoid=config.Zenhub_repo_Id,issue_id=items['issue_number'])
            changes={}
            G_name=issue.title
            G_description=issue.body
            try:
                Z_status=getTranslationData(json.load(open('zen2ahaMap.json')),zen_issue_detail['pipeline']['name'])
            except:
                if('pipeline' not in zen_issue_detail and issue.state =='closed'):
                    Z_status=getTranslationData(json.load(open('zen2ahaMap.json')),issue.state)
                else:
                    Z_status=None
            G_Release=issue.milestone.title if issue.milestone is not None else None
            Aha_MF=getMasterFeatureDetailAha(aha_epic['aha_ref_num'])        
            if(Aha_MF is not None):
                Aha_MF=Aha_MF['master_feature']
                A_name=Aha_MF['name']
                A_description=Aha_MF['description']['body']
                A_status=Aha_MF['workflow_status']['name']
                A_release_id=Aha_MF['release']['reference_num']

                if(A_name!=G_name):
                    changes['name']=G_name

                if(A_description!=G_description):
                    changes['description']=G_description

                if(A_status!=Z_status):
                    changes['workflow_status']={'name':Z_status}

                if(G_Release !=None and config.update_release_dates):
                    if(getTranslationData( Aha_releases,G_Release) is not None ) :
                        if(A_release_id!=getTranslationData( Aha_releases,G_Release)['reference_num']):
                            changes['release_id']=Aha_releases[G_Release]['id']
                if(Aha_MF['start_date']!= Aha_MF['release']['start_date'] and config.update_release_dates):
                    changes['start_date']=Aha_MF['release']['start_date']
                    
                if(Aha_MF['due_date']!= Aha_MF['release']['release_date'] and config.update_release_dates):
                    changes['due_date']=Aha_MF['release']['release_date']
                if(config.Track_due_date and issue.milestone is not None):
                    if(Aha_MF['due_date']!=str(issue.milestone.due_on.date())):
                        changes['due_date']=str(issue.milestone.due_on.date())
                
                ############Mapping Releases to Master features on Aha
                try:
                    Release_in_ZH= ZH_ISSUE_RELEASE_MAP[str(items['issue_number'])]
                    if(Aha_MF['release'] is not None):
                        Release_in_AHA= Aha_MF['release']['id']
                    else:
                        Release_in_AHA=None
                
                    Translation= ENDURANCE_RELEASES[Release_in_ZH] 
                    if(Release_in_AHA != Translation['aha_release_id']):
                        changes['release']=Translation['aha_release_id']

                except KeyError:    
                    logger.error("Unable to Find respective ZH release on the Endurance")
                #######################################################

                if(changes!={}):
                    update_response=updateMasterFeatureAha(aha_epic['aha_ref_num'],changes=changes)
                    if(update_response.status_code==200):
                        
                        logger.info("UPDATED"+str(aha_epic)+str(changes))
                        
                        final_Changes.append("updated!:  "+ str(aha_epic) + str(changes))
                    else:
                        logging.error("Error while updating.."+ str(update_response.status_code)+ str(update_response.content))
                else:
                    logger.info('NO CHANGE! '+ str(aha_epic))
                    
    
    update_to_endurance=requests.post(config.Endurance_Source,headers={'x-api-key':config.ndurance_key,'Content-Type':'application/json'}, data= json.dumps(ENDURANCE))
    if(update_to_endurance.status_code==201):
        logging.info("successfully updated status to endurance")
    else:
        logging.error("Non 200 code from ndurance"+str(update_to_endurance.status_code))
    
    return final_Changes
#main()
##end
