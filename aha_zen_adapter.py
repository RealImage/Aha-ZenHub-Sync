import requests
import sys
import json
from autologging import logged,traced,TRACE 
import logging
import time
from objectifier import Objectifier
import os
import argparse
from datetime import datetime
#import config
import github3
from urllib.parse import urljoin
import releases

logging.basicConfig(level=logging.INFO,
 format="%(levelname)s:%(filename)s,%(lineno)d:%(name)s.%(funcName)s:%(message)s", 
  handlers=[logging.StreamHandler()])
logger=logging.getLogger()


config= json.loads(os.environ.get('config'))
config=Objectifier(config)


AHA_TOKEN=config.AHA_TOKEN
ZENHUB_TOKEN=config.ZENHUB_TOKEN
AHA_HEADER={'Authorization':AHA_TOKEN,'Content-Type': "application/json","User-Agent":"allandavid35@gmail.com"}
ZENHUB_HEADER={'X-Authentication-Token':ZENHUB_TOKEN}
GITHUB_TOKEN=config.GITHUB_TOKEN
ZH_ISSUE_RELEASE_MAP={}
map_data= json.load(open('zen2ahaMap.json'))

########################DATA_STORE##################################
ENDURANCE= requests.get(config.Endurance_Source, headers={'x-api-key':config.ndurance_key}).json()
ENDURANCE_RELEASES= requests.get(config.Endurance_Source_3, headers={'x-api-key':config.ndurance_key}).json()
####################################################################

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



#create an instance of github_object and return the same
def github_object(TOKEN,repository):
    repository=repository
    gh = github3.GitHub(token=TOKEN)
    owner,name=repository.split('/',1)
    repo= gh.repository(owner,name)
    return repo

#Get all the features along with their Ids and referencenumbers  | Rate limit protection : True
def getFeatureListFromAha():
    features=[] 
    total_page=9
    current_page=1
    
    while current_page<=total_page:
        time.sleep(0.5)
        rs= requests.get(urljoin(config.Aha_Domain,'/api/v1/products/{product_id}/features'.format(product_id=config.product_id)), params={'page':current_page} ,headers=AHA_HEADER)
        if(rs.status_code==200):
            feature_set=rs.json()
            for items in feature_set['features']:
                features.append(items)
            current_page=feature_set['pagination']['current_page'] + 1
            total_page=feature_set['pagination']['total_pages']
        elif(rs.status_code==429):
            logger.error('Rate limited at Aha! sleeping for 10 seconds')
            time.sleep(10)
        elif(rs.status_code==403):
            logger.error('Authentication Failure at Aha! Stopping process')
            sys.exit(1)
        else:
            logger.error('Non 200 error code returned by Aha! {0}'.format(str(rs.status_code)))
            sys.exit(1)
            
    logger.info('returned Features Array {0}'.format(str(len(features))))
    return features

#Get Translation data
def getTranslationData(jsoncontent,key):
    try:
        return jsoncontent[key]
    except KeyError:
        logging.error("The requested translation data {0} is not found on the map".format(key))
        return None


#Get Details of a given feature  from Aha | Rate limit protection : True
def getFeatureDetailFromAha(reference_num):
    rs= requests.get(urljoin(config.Aha_Domain,'/api/v1/features/'+reference_num) , headers=AHA_HEADER)
    if(rs.status_code==200):
        return rs.json()['feature']
    elif(rs.status_code==429):
        #Handle Ratelimits
        logger.error('Encountered Rate Limit while getting issue detail from Aha! , sleeping 10 secs')
        time.sleep(10)
        return getFeatureDetailFromAha(reference_num)
    else:
        return None


#Get Details for a given issue from Zen  | Rate limit protection : True
def getIssueDetailFromZen(repoid,issue_id):
    rs= requests.get(urljoin(config.Zenhub_Domain,'/p1/repositories/{0}/issues/{1}'.format(str(repoid),str(issue_id))),headers=ZENHUB_HEADER )
    if(rs.status_code==200):
        result= rs.json()
        result['id']=issue_id
        return result
    elif(rs.status_code==429):
        logger.error('Encountered Rate Limit while getting Issue detail from Zen! sleeping 10 secs')
        time.sleep(10)
        return getIssueDetailFromZen(repoid,issue_id)
    else:
        #Log error
        return None


#Get details of an epic from Zenhub | Rate limit protection : True
def getEpicDetailfromZen(repoid,epic_id): 
    rs=requests.get(urljoin(config.Zenhub_Domain,'/p1/repositories/{0}/epics/{1}'.format(repoid,epic_id)),headers=ZENHUB_HEADER)
    if(rs.status_code==200):
        return rs.json()
    elif(rs.status_code==429):
        #handle ratelimit
        time.sleep(10)
        return getEpicDetailfromZen(repoid,epic_id)
    else:
        return None

#
def buildEpicStoryMap(repoid):
    All_Epics=None
    issue_epic_map={}
    rs=requests.get(urljoin(config.Zenhub_Domain,'/p1/repositories/{0}/epics/'.format(repoid)),headers=ZENHUB_HEADER)
    if(rs.status_code==200):
        All_Epics=rs.json()
    for items in All_Epics['epic_issues']:
        epic_data=getEpicDetailfromZen(repoid,items['issue_number'])
        if(epic_data is not None):
            for issues in epic_data['issues']:
                if(str(issues['repo_id'])==repoid):
                    issue_epic_map[str(issues['issue_number'])]=items['issue_number']
    return issue_epic_map

EPIC_MAP=buildEpicStoryMap(config.Zenhub_repo_Id)


#Compare status and generate diff 
def generatediff(Aha_feature,Zen_issue, Git_issue=None , repo_id=None):
    zen=Objectifier(Zen_issue)
    Aha=Objectifier(Aha_feature)
    changes=[]
    try:
        if(zen.pipeline is None and Aha.workflow_status.name != 'Released'):
            changes.append({'workflow_status':{"name":getTranslationData(map_data,'Closed')}})   
        elif(Aha.workflow_status.name != getTranslationData(map_data,zen.pipeline.name) and getTranslationData(map_data,zen.pipeline.name) is not None):
            changes.append({'workflow_status':{"name":getTranslationData(map_data,zen.pipeline.name)}})   
        if(zen.estimate is not None):             
            if(Aha.original_estimate!=zen.estimate.value):
                changes.append({'original_estimate':zen.estimate.value}) # Update Estimate
        if(zen.is_epic==False):
            try:
                Aha_Epic=Aha.master_feature.reference_num
            except:
                Aha_Epic=None
            try:
                Zen_Epic=ENDURANCE[str(EPIC_MAP[zen.id])]['aha_ref_num']
            except:
                Zen_Epic=None
            try:
             if(Aha_Epic!=Zen_Epic and Zen_Epic is not None):
                 changes.append({'master_feature':Zen_Epic})
            except:
             logger.error("Error occured during processing Master feature update")
            ####Updating start and end date as per release date:
            try:
             if(Aha.release is not None and config.features_source_of_release_date.lower()=='zenhub'):
                 if(Aha.release.start_date!=Aha.start_date):
                     changes.append({'start_date':Aha.release.start_date})
                 if(Aha.release.release_date!=Aha.due_date):
                     changes.append({'due_date':Aha.release.release_date})
             elif(config.features_source_of_release_date.lower()=='github' and Git_issue is not None and Git_issue.milestone is not None):
                 start_date_from_Zen = get_milestone_start_date_from_zen(repo_id,Git_issue.milestone.number).split('T')[0]
                 due_date_from_Zen = str(Git_issue.milestone.due_on.date())
                 if(Aha.start_date != start_date_from_Zen ):
                     changes.append({'start_date':start_date_from_Zen})
                 if(Aha.due_date != due_date_from_Zen):
                     changes.append({'due_date':str(Git_issue.milestone.due_on.date())})
            except:
             logger.error("Error occured during start date and due date update")
            ############################################

            ###### Handle Releases######################
            try:
                Release_in_ZH= ZH_ISSUE_RELEASE_MAP[zen.id] # ZH's Release ID for this Issue
                Release_in_AHA= Aha.release.id              # Aha's Release ID
            
                Translation= ENDURANCE_RELEASES[Release_in_ZH] 
                if(Release_in_AHA != Translation['aha_release_id']):
                    changes.append({'release':Translation['aha_release_id']})
            except KeyError:
                logger.error("Unable to Find respective ZH release on the Endurance or the release is not mapped to the feature on ZH")
                
            ######################

    except Exception as e:
        logger.error("Error was encountered during update ")
    return changes

#Update details on to aha and Log the same in detail  | Rate Limit : Cant make more than 1 request per second  
def update_aha(Aha_id,patchdata,skips=[], include=[]):
    time.sleep(1)
    update_data_schema={
        "feature":{}
    }
    if(len(patchdata)==0):
        logger.info(Aha_id+"  No Update found!")
        return 0
    elif(Aha_id not in skips):# and Aha_id=='QS-13'):
        
        for items in patchdata:
            update_data_schema['feature'].update(items)                
        rs=requests.put(urljoin(config.Aha_Domain,'/api/v1/features/{0}'.format(Aha_id)), headers=AHA_HEADER , data=json.dumps(update_data_schema))
        if(rs.status_code==200):
            logger.info(Aha_id+" "+str(update_data_schema))
            return 1
        else:
            logger.error(Aha_id+' Oops something Went wrong while updating'+ str(rs.status_code)+' '+ json.dumps(update_data_schema))
            return -1
    #REMOVE THIS
    else:
        return 0
def arg_parser():
    args = argparse.ArgumentParser(
        description='Sync Status and Estimates from Zenhub to Aha!'
    )
    args.add_argument(
        '--skip',
        help='If we want to skip syncing of few features, we can specify them in this by using the sync flag. Eg "QS-14","QS-15" ..',
         dest='skip', required=False, default=[],
    )


    return args



def get_milestone_start_date_from_zen(repo_id,milestone_number):
    rs= requests.get(urljoin(config.Zenhub_Domain,'p1/repositories/{0}/milestones/{1}/start_date'.format(repo_id,milestone_number)), headers=ZENHUB_HEADER)
    if(rs.status_code==200):
        return rs.json()['start_date']
    else:
        return None



def main(skip=[]):
    change_log={'count':0,'errors':0,'changes':[]}
    #get feature list from aha
    FeatureList=getFeatureListFromAha()
    git_repo=github_object(GITHUB_TOKEN,config.repo_name)
    global ZH_ISSUE_RELEASE_MAP
    ZH_ISSUE_RELEASE_MAP= build_Release_Map_ZH()
    for items in FeatureList:
        if(items['reference_num']=='QS-797' or items['reference_num']=='QS-290'):
            print('mouse')
        AhaFeature=getFeatureDetailFromAha(items['reference_num'])
        compound_id=str(list( filter(lambda types: types['name'] == 'compound_id', AhaFeature['integration_fields']) )[0]['value'])
        repoId=compound_id.split('/')[0]
        issueId=compound_id.split('/')[1]
        ZenIssue=getIssueDetailFromZen(repoId,issueId)
        try: #Very Randomly this piece of code returns a 502, so will attempt to retry once before crashing
            github_issue_object=git_repo.issue(issueId)
        except:
            github_issue_object=git_repo.issue(issueId)
        diff=generatediff(AhaFeature,ZenIssue, Git_issue=github_issue_object, repo_id= repoId)
        state=update_aha(items['reference_num'],diff)
        if(state>0):
            change_log['count']=change_log['count']+1
            change_log['changes'].append({items['reference_num']:diff})
        elif(state<0):
            change_log['errors']=change_log['errors']+1
        
    logger.info(str(change_log))
    return change_log['changes']



