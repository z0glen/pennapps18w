import boto3
import json
import sys
from PIL import Image, ImageFont, ImageDraw, ImageEnhance
import logging
from tmdb3 import *
from aws import *
import time

logger = logging.getLogger('mainlog')

reload(sys)
sys.setdefaultencoding("UTF-8")

set_key('<key>')

def uploadFile(filename):
        s3_client.upload_file('./tmp/'+filename, 'pennapps-retro', filename)

def detectFaces(filename_raw):
    logger.debug("Filename: " + str(filename_raw))
    filename = filename_raw.lower()

    ################################
    #FIX THIS
    ################################
    '''
    files = bucket.get_available_subresources()
    if(filename not in files):
        logger.error("Filename not found on server")
        sys.exit()
    '''

    # Detect the format of the input file
    video_ext = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv']
    img_ext = ['.jpg', '.jpeg', '.tiff', '.png', '.bmp']

    fileType = ''

    for item in video_ext:
        if item in filename:
            fileType = 'video'
            logger.info("File is video")

    for item in img_ext:
        if item in filename:
            fileType = 'image'
            logger.info("File is image")

    if(fileType == ''):
        logger.critical("File extension not recognized")
        sys.exit()

    if(fileType == 'image'):
        # Download image
        logger.info("Downloading File...")
        s3_client.download_file("pennapps-retro", filename_raw, './'+filename)
        logger.info("Got file")

        # Get image size
        pilObject = Image.open(filename)
        imWidth, imHeight = pilObject.size
        logger.debug("Image size: " + str(imWidth) + ", " + str(imHeight))

        # Find faces
        logger.info("Finding faces...")
        img_resp = celeb_img(filename)

        print "Unrecognized faces: " + str(len(img_resp['UnrecognizedFaces']))

        # Create list to hold the box coordinates for each face
        faces = []

        for item in img_resp['CelebrityFaces']:
            confidence = int(item['MatchConfidence'])
            if(confidence > 60):
                name = str(item['Name'])
                if(item['Urls']):
                    box = [(int(imWidth*item['Face']['BoundingBox']['Left']), int(imHeight*(item['Face']['BoundingBox']['Top'] + item['Face']['BoundingBox']['Height']))), (int(imWidth*(item['Face']['BoundingBox']['Left']+item['Face']['BoundingBox']['Width'])), int(imHeight*(item['Face']['BoundingBox']['Top'])))]
                    logger.info("Name: " + str(item['Name']) + ".   Confidence:  " + str(item['MatchConfidence']) + "%")
                    faces.append([name, confidence, box])


    elif(fileType == 'video'):
        # Find faces
        job_ID = initialize_video(filename_raw)
        [vid_resp, stat] = celeb_vid(job_ID)
        while('SUCCEEDED' not in stat):
            time.sleep(2)
            [vid_resp, stat] = celeb_vid(job_ID)

        # Create list to hold the faces
        faces = []
        names = []

        logger.debug("Sorting faces...")

        for item in vid_resp['Celebrities']:
            confidence = int(item['Celebrity']['Confidence'])
            if(confidence > 80):
                name = str(item['Celebrity']['Name'])
                if(item['Celebrity']['Urls'] and not name in names):
                    names.append(name)
                    logger.info("Name: " + str(name) + ".   Confidence:  " + str(confidence) + "%")
                    faces.append([name, confidence])

    # Print the found faces
    logger.debug(faces)


    if(fileType == 'image'):
        # Draw boxes on faces
        source_img = Image.open(filename).convert('RGB')
        img = Image.new("RGBA", source_img.size, (0, 0, 0, 0))
        for face in faces:
            draw1 = ImageDraw.Draw(source_img, 'RGBA')
            draw1.rectangle((face[2][0], face[2][1]), outline=(255, 0, 0))
            img_rectangle = Image.composite(img, source_img, img)

            draw2 = ImageDraw.Draw(img, "RGBA")
            draw2.text((face[2][0][0], face[2][0][1]+10), face[0], font=ImageFont.truetype('/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf', 45), fill=(255, 0, 0))


        Image.composite(img, source_img, img).save(filename[:-4]+'-out.jpg', "JPEG")


    # If one or zero faces are detected, no results can be drawn
    if(len(faces) <= 1):
        logger.warning("Not enough actors found, no recommendation can be made.  Found: " + str(len(faces)))
        sys.exit()

    # Get roles for each identified face in list of lists
    titles = []
    logger.info("Getting person info...")
    for person in faces:
        titles.append([])
        res = searchPerson(person[0])
        roles = res[0].roles
        for role in roles:
            titles[len(titles)-1].append(role.title)

    logger.debug(titles)

    # Find the common titles between all actors
    logger.info("Finding common movies...")
    result = set(titles[0]).intersection(set(titles[1]))
    for i in range(2, len(titles)):
        result = result.intersection(set(titles[i]))

    # If there are no common movies between these actors
    # attempt to find common movies with n-1 actors
    if(len(result) == 0 and len(faces) <= 2):
        logger.warning("Could not find common movie, not enough actors remaining")
        sys.exit()

    elif(len(result) == 0 and len(faces) > 2):
        logger.debug("Couldn't find common movie, trying n-1 actors")
        shortActorList = [] # Create the empty list to hold n-1 actors
        for i in range(0, len(titles)):
            shortActorList.append(titles[0:i]+titles[i+1:])

        # Look for a movie in any of the n-1 actor lists
        for shortList in shortActorList:
            result = set(shortList[0]).intersection(set(shortList[1]))
            for i in range(2, len(shortList)):
                result = result.intersection(set(shortList[i]))

            if(len(result) == 0):
                logger.warning("No movies found")
            else:
                for title in result:
                    genres = searchMovie(title)[0].genres
                    for genre in genres:
                        if('Animation' in genre.name):
                            animationFlag = 1
                    if(not animationFlag):
                        logger.info("This movie could be " + str(title))

    else:
        for title in result:
            animationFlag = 0
            genres = searchMovie(title)[0].genres
            for genre in genres:
                if('Animation' in genre.name):
                    animationFlag = 1
            if(not animationFlag):
                logger.info("This movie could be " + str(title))
