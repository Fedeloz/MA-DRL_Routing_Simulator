import time
import pandas as pd
import math
import numpy as np
import geopy.distance
import matplotlib.pyplot as plt
import pylab
import matplotlib
import simpy
import numba
import networkx as nx
from PIL import Image
from scipy.optimize import linear_sum_assignment
import pickle
import random
import os
import folium
from IPython.display import display
from typing import List, Tuple
from datetime import datetime
import seaborn as sns
import gc
import cProfile
from matplotlib.colors import LogNorm


###############################################################################
################################    Log file    ###############################
###############################################################################

import sys
import atexit

class Logger(object):
    def __init__(self, filename='logfile.log'):
        self.terminal = sys.stdout
        self.log = open(filename, 'a')
        atexit.register(self.close)  # Register the close method to be called when the program exits

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        if not self.log.closed:
            self.log.flush()

    def close(self):
        if not self.log.closed:
            self.log.close()


###############################################################################
########################    Deep Learning Framework    ########################
###############################################################################

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import Model, Sequential, losses
from tensorflow.keras.layers import Dense, Embedding, Reshape, Input, Conv2D, Flatten
# from tensorflow.keras.optimizers import Adam
# from tensorflow.keras.optimizers.legacy import Adam  # Optimized for mac M1-M2
from collections import deque

# Forcing TensorFlow to use GPU
physical_devices = tf.config.list_physical_devices('GPU')
if len(physical_devices) > 0:
    # tf.config.experimental.set_memory_growth(physical_devices[0], True)
    print('GPU(s) available:')
    print(physical_devices)
else:
    print('No GPU available')

###############################################################################
###############################    Constants    ###############################
###############################################################################

# HOT PARAMS
pathings    = ['hop', 'dataRate', 'dataRateOG', 'slant_range', 'Q-Learning', 'Deep Q-Learning']
pathing     = pathings[5]# dataRateOG is the original datarate. If we want to maximize the datarate we have to use dataRate, which is the inverse of the datarate
distanceRew = 3          # 1: Distance reward normalized to total distance.
                         # 2: Distance reward normalized to average moving possibilities
                         # 3: Distance reward normalized to maximum close up
                         # 4: Distance reward normalized by 2.000 km

drawDeliver = True      # create pictures of the path every 1/10 times a data block gets its destination
Train       = True      # Global for all scenarios with different number of GTs. if set to false, the model will not train any of them
MIN_EPSILON = 0.01      # Minimum value that the exploration parameter can have 
importQVals = False     # imports either QTables or NN from a certain path
explore     = True      # If True, makes random actions eventually, if false only exploitation
mixLocs     = False      # If true, every time we make a new simulation the locations are going to change their order of selection
balancedFlow= False     # if set to true all the generated traffic at each GT is equal
gamma       = 0.6       # greedy factor

w1          = 3         # rewards the getting to empty queues
w2          = 20        # rewards getting closes phisically    

# number of gateways to be tested
GTs = [2]
# GTs = [i for i in range(2,19)] # 19.

CurrentGTnumber = -1    # This number will be updating as the number of Gateways change. In the simulation it will iterate the GTs list

# Physical constants
rKM = 500               # radio in km of the coverage of each gateway
Re  = 6378e3            # Radius of the earth [m]
G   = 6.67259e-11       # Universal gravitational constant [m^3/kg s^2]
Me  = 5.9736e24         # Mass of the earth
Te  = 86164.28450576939 # Time required by Earth for 1 rotation
Vc  = 299792458         # Speed of light [m/s]
k   = 1.38e-23          # Boltzmann's constant
eff = 0.55              # Efficiency of the parabolic antenna

# Downlink parameters
f       = 20e9  # Carrier frequency GEO to ground (Hz)
B       = 500e6 # Maximum bandwidth
maxPtx  = 10    # Maximum transmission power in W
Adtx    = 0.26  # Transmitter antenna diameter in m
Adrx    = 0.33  # Receiver antenna diameter in m
pL      = 0.3   # Pointing loss in dB
Nf      = 1.5   # Noise figure in dB
Tn      = 50    # Noise temperature in K
min_rate= 10e3  # Minimum rate in kbps

# Uplink Parameters
# balancedFlow= True        # if set to true all the generated traffic at each GT is equal
totalFlow   = 2*1000000000  # Total average flow per GT when the balanced traffc option is enabled. Malaga has 3*, LA has 3*, Nuuk/500
avUserLoad  = 8593 * 8      # average traffic usage per second in bits

# Block
blockSize   = 64800

# Movement
movementTime= 10 * 3600 # should be in the order of 10's of hours. If the test is not 'Rates', the movement time is still kept large to avoid the constellation moving
ndeltas     = 25        # This number will multiply deltaT. If bigger, will make the roatiorotation distance bigger

# Deep & Q Learning
# importQVals = False     # imports either QTables or NN from a certain path
printPath   = False     # plots the map with the path after every decision
alpha       = 0.25      # learning rate for Q-Tables
# gamma       = 0.6       # greedy factor
epsilon     = 0.1       # exploration factor for Q-Learning ONLY
tau         = 0.1       # rate of copying the weights from the Q-Network to the target network
learningRate= 0.001     # Default learning rate for Adam optimizer
# drawDeliver = True      # create pictures of the path every 1/10 times a data block gets its destination
GridSize    = 8         # Earth divided in GridSize rows for the grid. Used to be 15
winSize     = 20       # window size for the representation in the plots
markerSize  = 50        # Size of the markers in the plots
nTrain      = 2         # The DNN will train every nTrain steps

# Queues
infQueue    = 5000      # Upper boundary from where a queue is considered as infinite when obserbing the state
queueVals   = 10        # Values that the observed Queue can have, being 0 the best (Queue of 0) and max the worst (Huge queue or inexistent link).

# rewards
ArriveReward= 10        # Reward given to the system in case it sends the data block to the satellite linked to the destination gateway
# w1          = 1         # rewards the getting to empty queues
# w2          = 20        # rewards getting closes phisically     
againPenalty= -0.5      # Penalty if the satellite sends the block to a hop where it has already been
unavPenalty = -0.5      # Penalty if the satellite tries to send the block to a direction where there is no linked satellite

# Deep Learning
MAX_EPSILON = 0.99      # Maximum value that the exploration parameter can have
# MIN_EPSILON = 0.91      # Minimum value that the exploration parameter can have
LAMBDA      = 0.0005    # This value is used to decay the epsilon in the deep learning implementation
decayRate   = 4         # sets the epsilon decay in the deep learning implementatio. If higher, the decay rate is slower. If lower, the decay is faster
Clipnorm    = 1         # Maximum value to the nom of the gradients. Prevents the gradients of the model parameters with respect to the loss function becoming too large
hardUpdate  = 1         # if up, the Q-network weights are copied inside the target network every updateF iterations. if down, this is done gradually
updateF     = 1000      # every updateF updates, the Q-Network will be copied inside the target Network. This is done if hardUpdate is up
batchSize   = 16        # batchSize samples are taken from bufferSize samples to train the network
bufferSize  = 50        # bufferSize samples are used to train the network

# Stop Loss
# Train       = True      # Global for all scenarios with different number of GTs. if set to false, the model will not train any of them
stopLoss    = False     # activates the stop loss function
nLosses     = 50        # Nº of loss samples used for the stop loss
lThreshold  = 0.5       # If the mean of the last nLosses are lower than lossThreshold, the mdoel stops training
TrainThis   = Train     # Local for a single scenario with a certain number of GTs. If the stop loss is activated, this will be set to False and the scenario will not train anymore. 
                        # When another scenario is about to run, TrainThis will be set to Train again

###############################################################################
###############################      Paths      ###############################
###############################################################################

# nnpath = f'./Results/latency Test/Deep Q-Learning/qNetwork_{self.destinations}GTs.h5'
# nnpath = f'./latency Test/Deep Q-Learning/qNetwork_{self.destinations}GTs.h5'
# nnpath          = './pre_trained_NNs/qNetwork_10GTs.h5'
if __name__ == '__main__':
    nnpath          = ''
    outputPath      = './Results/latency Test/{}_{}s_[{}]_Del_[{}]_w1_[{}]_w2_{}_GTs/'.format(pathing, float(pd.read_csv("inputRL.csv")['Test length'][0]), ArriveReward, w1, w2, GTs)
    populationMap   = 'Population Map/gpw_v4_population_count_rev11_2020_15_min.tif'

###############################################################################
#################################    Simpy    #################################
###############################################################################

receivedDataBlocks  = []
createdBlocks       = []
seed                = np.random.seed(1)
upGSLRates          = []
downGSLRates        = []
interRates          = []
intraRate           = []


def getBlockTransmissionStats(timeToSim, GTs, constellationType, earth):
    '''
    General Block transmission stats
    '''
    allTransmissionTimes = []
    largestTransmissionTime = (0, None)
    mostHops = (0, None)
    queueLat = []
    txLat = []
    propLat = []
    # latencies = [queueLat, txLat, propLat]
    blocks = []
    allLatencies= []
    pathBlocks  = [[],[]]
    first       = earth.gateways[0]
    second      = earth.gateways[1]

    earth.pathParam

    for block in receivedDataBlocks:
        blocks.append(BlocksForPickle(block))
        time = block.getTotalTransmissionTime()
        hops = len(block.checkPoints)

        if largestTransmissionTime[0] < time:
            largestTransmissionTime = (time, block)

        if mostHops[0] < hops:
            mostHops = (hops, block)

        allTransmissionTimes.append(time)

        queueLat.append(block.getQueueTime()[0])
        txLat.append(block.txLatency)
        propLat.append(block.propLatency)
        
        # [creation time, total latency, arrival time, source, destination, block ID, queue time, transmission latency, prop latency]
        allLatencies.append([block.creationTime, block.totLatency, block.creationTime+block.totLatency, block.source.name, block.destination.name, block.ID, block.getQueueTime()[0], block.txLatency, block.propLatency])
        # pre-process the received data blocks. create the rows that will be saved in csv
        if block.source == first and block.destination == second:
            pathBlocks[0].append([block.totLatency, block.creationTime+block.totLatency])
            pathBlocks[1].append(block)
        
    # save congestion test data
    blockPath = f"./Results/Congestion_Test/{pathing} {float(pd.read_csv('inputRL.csv')['Test length'][0])}/"
    os.makedirs(blockPath, exist_ok=True)
    try:
        global CurrentGTnumber
        np.save("{}blocks_{}".format(blockPath, CurrentGTnumber), np.asarray(blocks),allow_pickle=True)
    except pickle.PicklingError:
        print('Error with pickle and profiling')

    avgTime = np.mean(allTransmissionTimes)
    totalTime = sum(allTransmissionTimes)

    print("\n########## Results #########\n")
    print(f"The simulation took {timeToSim} seconds to run")
    print(f"A total of {len(createdBlocks)} data blocks were created")
    print(f"A total of {len(receivedDataBlocks)} data blocks were transmitted")
    print(f"A total of {len(createdBlocks) - len(receivedDataBlocks)} data blocks were stuck")
    print(f"Average transmission time for all blocks were {avgTime}")
    print('Total latecies:\nQueue time: {}%\nTransmission time: {}%\nPropagation time: {}%'.format(
        '%.4f' % float(sum(queueLat)/totalTime*100),
        '%.4f' % float(sum(txLat)/totalTime*100),
        '%.4f' % float(sum(propLat)/totalTime*100)))

    results = Results(finishedBlocks=blocks,
                      constellation=constellationType,
                      GTs=GTs,
                      meanTotalLatency=avgTime,
                      meanQueueLatency=np.mean(queueLat),
                      meanPropLatency=np.mean(propLat),
                      meanTransLatency=np.mean(txLat),
                      perQueueLatency = sum(queueLat)/totalTime*100,
                      perPropLatency = sum(propLat)/totalTime*100,
                      perTransLatency = sum(txLat)/totalTime*100)

    return results, allLatencies, pathBlocks


def simProgress(simTimelimit, env):
    timeSteps = 100
    timeStepSize = simTimelimit/timeSteps
    progress = 1
    startTime = time.time()
    yield env.timeout(timeStepSize)
    while True:
        elapsedTime = time.time() - startTime
        estimatedTimeRemaining = elapsedTime * (timeSteps/progress) - elapsedTime
        print("Simulation progress: {}% Estimated time remaining: {} seconds Current simulation time: {}".format(progress, int(estimatedTimeRemaining), env.now), end='\r')
        yield env.timeout(timeStepSize)
        progress += 1


###############################################################################
###############################     Classes    ################################
###############################################################################


class Results:
    def __init__(self, finishedBlocks, constellation, GTs, meanTotalLatency, meanQueueLatency, meanTransLatency, meanPropLatency, perQueueLatency, perPropLatency,perTransLatency):

        self.GTs = GTs
        self.finishedBlocks = finishedBlocks
        self.constellation = constellation
        self.meanTotalLatency = meanTotalLatency
        self.meanQueueLatency = meanQueueLatency
        self.meanPropLatency = meanPropLatency
        self.meanTransLatency = meanTransLatency
        self.perQueueLatency = perQueueLatency
        self.perPropLatency = perPropLatency
        self.perTransLatency = perTransLatency


class BlocksForPickle:
    def __init__(self, block):
        self.size = blockSize  # size in bits
        self.ID = block.ID  # a string which holds the source id, destination id, and index of the block, e.g. "1_2_12"
        self.timeAtFull = block.timeAtFull  # the simulation time at which the block was full and was ready to be sent.
        self.creationTime = block.creationTime  # the simulation time at which the block was created.
        self.timeAtFirstTransmission = block.timeAtFirstTransmission  # the simulation time at which the block left the GT.
        self.checkPoints = block.checkPoints  # list of simulation reception times at node with the first entry being the reception time at first sat - can be expanded to include the sat IDs at each checkpoint
        self.checkPointsSend = block.checkPointsSend  # list of times after the block was sent at each node
        self.path = block.path
        self.queueLatency = block.queueLatency  # total time acumulated in the queues
        self.txLatency = block.txLatency  # total transmission time
        self.propLatency = block.propLatency  # total propagation latency
        self.totLatency = block.totLatency  # total latency


class RFlink:
    def __init__(self, frequency, bandwidth, maxPtx, aDiameterTx, aDiameterRx, pointingLoss, noiseFigure,
                 noiseTemperature, min_rate):
        self.f = frequency
        self.B = bandwidth
        self.maxPtx = maxPtx
        self.maxPtx_db = 10 * math.log10(self.maxPtx)
        self.Gtx = 10 * math.log10(eff * ((math.pi * aDiameterTx * self.f / Vc) ** 2))
        self.Grx = 10 * math.log10(eff * ((math.pi * aDiameterRx * self.f / Vc) ** 2))
        self.G = self.Gtx + self.Grx - 2 * pointingLoss
        self.No = 10 * math.log10(self.B * k) + noiseFigure + 10 * math.log10(
            290 + (noiseTemperature - 290) * (10 ** (-noiseFigure / 10)))
        self.GoT = 10 * math.log10(eff * ((math.pi * aDiameterRx * self.f / Vc) ** 2)) - noiseFigure - 10 * math.log10(
            290 + (noiseTemperature - 290) * (10 ** (-noiseFigure / 10)))
        self.min_rate = min_rate

    def __repr__(self):
        return '\n Carrier frequency = {} GHz\n Bandwidth = {} MHz\n Transmission power = {} W\n Gain per antenna: Tx {}  Rx {}\n Total antenna gain = {} dB\n Noise power = {} dBW\n G/T = {} dB/K'.format(
            self.f / 1e9,
            self.B / 1e6,
            self.maxPtx,
            '%.2f' % self.Gtx,
            '%.2f' % self.Grx,
            '%.2f' % self.G,
            '%.2f' % self.No,
            '%.2f' % self.GoT,
        )


class FSOlink:
    def __init__(self, data_rate, power, comm_range, weight):
        self.data_rate = data_rate
        self.power = power
        self.comm_range = comm_range
        self.weight = weight

    def __repr__(self):
        return '\n Data rate = {} Mbps\n Power = {} W\n Transmission range = {} km\n Weight = {} kg'.format(
            self.data_rate / 1e6,
            self.power,
            self.comm_range / 1e3,
            self.weight)


class OrbitalPlane:
    def __init__(self, ID, h, longitude, inclination, n_sat, min_elev, firstID, env, earth):
        self.ID = ID 								# A unique ID given to every orbital plane = index in Orbital_planes, string
        self.h = h									# Altitude of deployment
        self.longitude = longitude					# Longitude angle where is intersects equator [radians]
        self.inclination = math.pi/2 - inclination	# Inclination of the orbit form [radians]
        self.n_sat = n_sat							# Number of satellites in plane
        self.period = 2 * math.pi * math.sqrt((self.h+Re)**3/(G*Me))	# Orbital period of the satellites in seconds
        self.v = 2*math.pi * (h + Re) / self.period						# Orbital velocity of the satellites in m/s
        self.min_elev = math.radians(min_elev)							# Minimum elevation angle for ground comm.
        self.max_alpha = math.acos(Re*math.cos(self.min_elev)/(self.h+Re))-self.min_elev	# Maximum angle at the center of the Earth w.r.t. yaw
        self.max_beta  = math.pi/2-self.max_alpha-self.min_elev								# Maximum angle at the satellite w.r.t. yaw
        self.max_distance_2_ground = Re*math.sin(self.max_alpha)/math.sin(self.max_beta)	# Maximum distance to a servable ground station
        self.earth = earth

        # Adding satellites
        self.first_sat_ID = firstID # Unique ID of the first satellite in the orbital plane

        self.sats = []              # List of satellites in the orbital plane
        for i in range(n_sat):
            self.sats.append(Satellite(self.first_sat_ID + str(i), int(self.ID), int(i), self.h, self.longitude, self.inclination, self.n_sat, env, self))

        self.last_sat_ID = self.first_sat_ID + str(len(self.sats) - 1) # Unique ID of the last satellite in the orbital plane

    def __repr__(self):
        return '\nID = {}\n altitude= {} km\n longitude= {} deg\n inclination= {} deg\n number of satellites= {}\n period= {} hours\n satellite speed= {} km/s'.format(
            self.ID,
            self.h/1e3,
            '%.2f' % math.degrees(self.longitude),
            '%.2f' % math.degrees(self.inclination),
            '%.2f' % self.n_sat,
            '%.2f' % (self.period/3600),
            '%.2f' % (self.v/1e3))

    def rotate(self, delta_t):
        """
        Rotates the orbit according to the elapsed time by adjusting the longitude. The amount the longitude is adjusted
        is based on the fraction the elapsed time makes up of the time it takes the Earth to complete a full rotation.
        """

        # Change in longitude and phi due to Earth's rotation
        self.longitude = self.longitude + 2*math.pi*delta_t/Te
        self.longitude = self.longitude % (2*math.pi)
        # Rotating every satellite in the orbital plane
        for sat in self.sats:
            sat.rotate(delta_t, self.longitude, self.period)


# @profile
class Satellite:
    def __init__(self, ID, in_plane, i_in_plane, h, longitude, inclination, n_sat, env, orbitalPlane, quota = 500, power = 10):
        self.ID = ID                    # A unique ID given to every satellite
        self.orbPlane = orbitalPlane    # Pointer to the orbital plane which the sat belongs to
        self.in_plane = in_plane        # Orbital plane where the satellite is deployed
        self.i_in_plane = i_in_plane    # Index in orbital plane
        self.quota = quota              # Quota of the satellite
        self.h = h                      # Altitude of deployment
        self.power = power              # Transmission power
        self.minElevationAngle = 30     # Value is taken from NGSO constellation design chapter

        # Spherical Coordinates before inclination (r,theta,phi)
        self.r = Re+self.h
        self.theta = 2 * math.pi * self.i_in_plane / n_sat
        self.phi = longitude

        # Inclination of the orbital plane
        self.inclination = inclination

        # Cartesian coordinates  (x,y,z)
        self.x = self.r * (math.sin(self.theta)*math.cos(self.phi) - math.cos(self.theta)*math.sin(self.phi)*math.sin(self.inclination))
        self.y = self.r * (math.sin(self.theta)*math.sin(self.phi) + math.cos(self.theta)*math.cos(self.phi)*math.sin(self.inclination))
        self.z = self.r * math.cos(self.theta)*math.cos(self.inclination)

        self.polar_angle = self.theta               # Angle within orbital plane [radians]
        self.latitude = math.asin(self.z/self.r)   # latitude corresponding to the satellite
        # longitude corresponding to satellite
        if self.x > 0:
            self.longitude = math.atan(self.y/self.x)
        elif self.x < 0 and self.y >= 0:
            self.longitude = math.pi + math.atan(self.y/self.x)
        elif self.x < 0 and self.y < 0:
            self.longitude = math.atan(self.y/self.x) - math.pi
        elif self.y > 0:
            self.longitude = math.pi/2
        elif self.y < 0:
            self.longitude = -math.pi/2
        else:
            self.longitude = 0

        self.waiting_list = {}
        self.applications = []
        self.n_sat = n_sat

        self.ngeo2gt = RFlink(f, B, maxPtx, Adtx, Adrx, pL, Nf, Tn, min_rate)
        self.downRate = 0

        # simpy
        self.env = env
        self.sendBufferGT = ([env.event()], [])  # ([self.env.event()], [DataBlock(0, 0, "0", 0)])
        self.sendBlocksGT = []  # env.process(self.sendBlock())  # simpy processes which send the data blocks
        self.sats = []
        self.linkedGT = None
        self.GTDist = None
        # list of data blocks waiting on their propagation delay.
        self.tempBlocks = []  # This list is used to so the block can have their paths changed when the constellation is moved

        self.intraSats = []
        self.interSats = []
        self.sendBufferSatsIntra = []
        self.sendBufferSatsInter = []
        self.sendBlocksSatsIntra = []
        self.sendBlocksSatsInter = []
        self.newBuffer = [False]

        self.QLearning = None   # Q-learning table that will be updated in case the pathing is 'Q-Learning'
        self.maxSlantRange = self.GetmaxSlantRange()

    def GetmaxSlantRange(self):
        """
        Maximum distance from satellite to edge of coverage area is calculated using the following formula:
        D_max(minElevationAngle, h) = sqrt(Re**2*sin**2(minElevationAngle) + 2*Re*h + h**2) - Re*sin(minElevationAngle)
        This formula is based on the NGSO constellation design chapter page 16.
        """
        eps = math.radians(self.minElevationAngle)

        distance = math.sqrt((Re+self.h)**2-(Re*math.cos(eps))**2) - Re*math.sin(eps)

        return distance

    def __repr__(self):
        return '\nID = {}\n orbital plane= {}, index in plane= {}, h={}\n pos r = {}, pos theta = {},' \
               ' pos phi = {},\n pos x= {}, pos y= {}, pos z= {}\n inclination = {}\n polar angle = {}' \
               '\n latitude = {}\n longitude = {}'.format(
                self.ID,
                self.in_plane,
                self.i_in_plane,
                '%.2f' % self.h,
                '%.2f' % self.r,
                '%.2f' % self.theta,
                '%.2f' % self.phi,
                '%.2f' % self.x,
                '%.2f' % self.y,
                '%.2f' % self.z,
                '%.2f' % math.degrees(self.inclination),
                '%.2f' % math.degrees(self.polar_angle),
                '%.2f' % math.degrees(self.latitude),
                '%.2f' % math.degrees(self.longitude))

    def createReceiveBlockProcess(self, block, propTime):
        """
        Function which starts a receiveBlock process upon receiving a block from a transmitter.
        """
        process = self.env.process(self.receiveBlock(block, propTime))

    def receiveBlock(self, block, propTime):
        """
        Simpy process function:

        This function is used to handle the propagation delay of data blocks. This is done simply by waiting the time
        of the propagation delay and adding the block to the send-buffer afterwards. Since there are multiple buffers,
        this function looks at the next step in the blocks path and adds the block to the correct send-buffer.
        When Q-Learning or Deep learning is used, this function is where the next step in the block's path is found.

        While the transmission delay is handled at the transmitter, the transmitter cannot also wait for the propagation
        delay, otherwise the send-buffer might be overfilled.

        Using this structure, if there are to be implemented limits on the sizes of the "receive-buffer" it could be
        handled by either limiting the amount of these processes that can occur at the same time, or limiting the size
        of the send-buffer.
        """
        # wait for block to fully propagate
        self.tempBlocks.append(block)

        yield self.env.timeout(propTime)

        if block.path == -1:
            return

        # KPI: propLatency receive block from sat
        block.propLatency += propTime

        for i, tempBlock in enumerate(self.tempBlocks):
            if block.ID == tempBlock.ID:
                self.tempBlocks.pop(i)
                break

        try: # ANCHOR Save Queue time csv
            block.queueTime.append((block.checkPointsSend[len(block.checkPointsSend)-1]- block.checkPoints[len(block.checkPoints)-1]))
        except IndexError:
            # print('Index error')
            pass

        block.checkPoints.append(self.env.now)

        # if QLearning or Deep Q-Learning we:
        # Compute the next hop in the path and add it to the second last position (Last is the destination gateway)
        # we let the (Deep) Q-model choose the next hop and it will be added to the block.QPath as mentioned
        # if the next hop is the linked gateway it will simply not add anything and will let the model work normally
        if ((self.QLearning) or (self.orbPlane.earth.DDQNA is not None)):
            if len(block.QPath) > 3: # the block does not come from a gateway
                if self.QLearning:
                    nextHop = self.QLearning.makeAction(block, self, self.orbPlane.earth.gateways[0].graph, self.orbPlane.earth, prevSat = (findByID(self.orbPlane.earth, block.QPath[len(block.QPath)-3][0])))
                else:
                    nextHop = self.orbPlane.earth.DDQNA.makeDeepAction(block, self, self.orbPlane.earth.gateways[0].graph, self.orbPlane.earth, prevSat = (findByID(self.orbPlane.earth, block.QPath[len(block.QPath)-3][0])))
            else:
                if self.QLearning:
                    nextHop = self.QLearning.makeAction(block, self, self.orbPlane.earth.gateways[0].graph, self.orbPlane.earth)
                else:
                    nextHop = self.orbPlane.earth.DDQNA.makeDeepAction(block, self, self.orbPlane.earth.gateways[0].graph, self.orbPlane.earth)

            if nextHop != 0:
                block.QPath.insert(len(block.QPath)-1 ,nextHop)
                pathPlot = block.QPath.copy()
                pathPlot.pop()
            else:
                pathPlot = block.QPath.copy()
            
            # If printPath plots an image for every action taken. Plots 1/10 of blocks. # ANCHOR plot action satellite
            #################################################################
            if self.orbPlane.earth.printPaths:
                if int(block.ID[len(block.ID)-1]) == 0:
                    os.makedirs(self.orbPlane.earth.outputPath + '/pictures/', exist_ok=True) # create output path
                    outputPath = self.orbPlane.earth.outputPath + '/pictures/' + block.ID + '_' + str(len(block.QPath)) + '_'
                    plotShortestPath(self.orbPlane.earth, pathPlot, outputPath)
            #################################################################

            path = block.QPath  # if there is Q-Learning the path will be repalced with the QPath
        else:
            path = block.path   # if there is no Q-Learning we will work with the path as normally

        # get this satellites index in the blocks path
        index = None
        for i, step in enumerate(path):
            if self.ID == step[0]:
                index = i

        if not index:
            print(path)

        # check if next step in path is GT (last step in path)
        if index == len(path) - 2:
            # add block to GT send-buffer
            if not self.sendBufferGT[0][0].triggered:
                self.sendBufferGT[0][0].succeed()
                self.sendBufferGT[1].append(block)
            else:
                newEvent = self.env.event().succeed()
                self.sendBufferGT[0].append(newEvent)
                self.sendBufferGT[1].append(block)

        else:
            ID = None
            isIntra = False
            # get ID of next sat
            for sat in self.intraSats:
                id = sat[1].ID
                if id == path[index + 1][0]:
                    ID = sat[1].ID
                    isIntra = True
            for sat in self.interSats:
                id = sat[1].ID
                if id == path[index + 1][0]:
                    ID = sat[1].ID

            if ID is not None:
                sendBuffer = None
                # find send-buffer for the satellite
                if isIntra:
                    for buffer in self.sendBufferSatsIntra:
                        if ID == buffer[2]:
                            sendBuffer = buffer
                else:
                    for buffer in self.sendBufferSatsInter:
                        if ID == buffer[2]:
                            sendBuffer = buffer
                # ANCHOR save the queue length that the block found at its next hop
                self.orbPlane.earth.queues.append(len(sendBuffer[1]))
                block.queue.append(len(sendBuffer[1]))

                # add block to buffer
                if not sendBuffer[0][0].triggered:
                    sendBuffer[0][0].succeed()
                    sendBuffer[1].append(block)
                else:
                    newEvent = self.env.event().succeed()
                    sendBuffer[0].append(newEvent)
                    sendBuffer[1].append(block)

            else:
                print(
                    "ERROR! Sat {} tried to send block to {} but did not have it in its linked satellite list".format(
                        self.ID, path[index + 1][0]))

    def sendBlock(self, destination, isSat, isIntra = None):
        """
        Simpy process function:

        Sends data blocks that are filled and added to one of the send-buffers, a buffer which consists of a list of
        events and data blocks. Since there are multiple send-buffers, the function finds the correct buffer given
        information regarding the desired destination satellite or GT. The function monitors the send-buffer, and when
        the buffer contains one or more triggered events, the function will calculate the time it will take to send the
        block and trigger an event which notifies a separate process that a block has been sent.

        A process is running this method for each ISL and for the downLink GSL the satellite has. This will usually be
        4 ISL processes and 1 GSL process.
        """

        if isIntra is not None:
            sendBuffer = None
            if isSat:
                if isIntra:
                    for buffer in self.sendBufferSatsIntra:
                        if buffer[2] == destination[1].ID:
                            sendBuffer = buffer
                else:
                    for buffer in self.sendBufferSatsInter:
                        if buffer[2] == destination[1].ID:
                            sendBuffer = buffer
        else:
            sendBuffer = self.sendBufferGT

        while True:
            try:
                yield sendBuffer[0][0]

                # ANCHOR KPI: queueLatency at sat
                sendBuffer[1][0].checkPointsSend.append(self.env.now)

                if isSat:
                    timeToSend = sendBuffer[1][0].size / destination[2]

                    propTime = self.timeToSend(destination)
                    yield self.env.timeout(timeToSend)

                    receiver = destination[1]

                else:
                    propTime = self.timeToSend(self.linkedGT.linkedSat)
                    timeToSend = sendBuffer[1][0].size / self.downRate
                    yield self.env.timeout(timeToSend)

                    receiver = self.linkedGT

                # When the constellations move, the only case where this process can simply continue, is when the
                # receiver is the same, and there is a block already ready to be sent. The only place where the process
                # can continue from, is as a result right here. Furthermore, the only processes this can happen for are
                # the inter-ISL processes.
                # Due to having to remake buffers when the satellites move, it is necessary for the process to "find"
                # the correct buffer again - the process uses a reference to the buffer: "sendBuffer".
                # To avoid remaking the reference every time a block is sent, the list of boolean values: self.newBuffer
                # is used to indicate when the constellation is moved,

                if True in self.newBuffer and not isIntra and isSat: # remake reference to buffer
                    if isIntra is not None:
                        sendBuffer = None
                        if isSat:
                            if isIntra:
                                for buffer in self.sendBufferSatsIntra:
                                    if buffer[2] == destination[1].ID:
                                        sendBuffer = buffer
                            else:
                                for buffer in self.sendBufferSatsInter:
                                    if buffer[2] == destination[1].ID:
                                        sendBuffer = buffer
                    else:
                        sendBuffer = self.sendBufferGT

                    for index, val in enumerate(self.newBuffer):
                        if val: # each process will one by one remake their reference, and change one value to True.
                                # After all processes has done this, all values are back to False
                            self.newBuffer[index] = False
                            break

                # ANCHOR KPI: txLatency ISL
                sendBuffer[1][0].txLatency += timeToSend
                receiver.createReceiveBlockProcess(sendBuffer[1][0], propTime)

                # remove from own buffer
                if len(sendBuffer[0]) == 1:
                    sendBuffer[0].pop(0)
                    sendBuffer[1].pop(0)
                    sendBuffer[0].append(self.env.event())

                else:
                    sendBuffer[0].pop(0)
                    sendBuffer[1].pop(0)
            except simpy.Interrupt:
                print(f'Simpy interrupt at sending block at satellite self.ID to {destination}')
                break

    def adjustDownRate(self):

        speff_thresholds = np.array(
            [0, 0.434841, 0.490243, 0.567805, 0.656448, 0.789412, 0.889135, 0.988858, 1.088581, 1.188304, 1.322253,
             1.487473, 1.587196, 1.647211, 1.713601, 1.779991, 1.972253, 2.10485, 2.193247, 2.370043, 2.458441,
             2.524739, 2.635236, 2.637201, 2.745734, 2.856231, 2.966728, 3.077225, 3.165623, 3.289502, 3.300184,
             3.510192, 3.620536, 3.703295, 3.841226, 3.951571, 4.206428, 4.338659, 4.603122, 4.735354, 4.933701,
             5.06569, 5.241514, 5.417338, 5.593162, 5.768987, 5.900855])
        lin_thresholds = np.array(
            [1e-10, 0.5188000389, 0.5821032178, 0.6266138647, 0.751622894, 0.9332543008, 1.051961874, 1.258925412,
             1.396368361, 1.671090614, 2.041737945, 2.529297996, 2.937649652, 2.971666032, 3.25836701, 3.548133892,
             3.953666201, 4.518559444, 4.83058802, 5.508076964, 6.45654229, 6.886522963, 6.966265141, 7.888601176,
             8.452788452, 9.354056741, 10.49542429, 11.61448614, 12.67651866, 12.88249552, 14.48771854, 14.96235656,
             16.48162392, 18.74994508, 20.18366364, 23.1206479, 25.00345362, 30.26913428, 35.2370871, 38.63669771,
             45.18559444, 49.88844875, 52.96634439, 64.5654229, 72.27698036, 76.55966069, 90.57326009])
        db_thresholds = np.array(
            [-100.00000, -2.85000, -2.35000, -2.03000, -1.24000, -0.30000, 0.22000, 1.00000, 1.45000, 2.23000, 3.10000,
             4.03000, 4.68000, 4.73000, 5.13000, 5.50000, 5.97000, 6.55000, 6.84000, 7.41000, 8.10000, 8.38000, 8.43000,
             8.97000, 9.27000, 9.71000, 10.21000, 10.65000, 11.03000, 11.10000, 11.61000, 11.75000, 12.17000, 12.73000,
             13.05000, 13.64000, 13.98000, 14.81000, 15.47000, 15.87000, 16.55000, 16.98000, 17.24000, 18.10000,
             18.59000, 18.84000, 19.57000])

        pathLoss = 10*np.log10((4*math.pi*self.linkedGT.linkedSat[0]*self.ngeo2gt.f/Vc)**2)
        snr = 10**((self.ngeo2gt.maxPtx_db + self.ngeo2gt.G - pathLoss - self.ngeo2gt.No)/10)
        shannonRate = self.ngeo2gt.B*np.log2(1+snr)

        feasible_speffs = speff_thresholds[np.nonzero(lin_thresholds <= snr)]
        speff = self.ngeo2gt.B * feasible_speffs[-1]

        self.downRate = speff

    def timeToSend(self, linkedSat):
        """
        Calculates the propagation time of a block going from satellite to satellite.
        """
        distance = linkedSat[0]
        pTime = distance/Vc
        return pTime

    def findNeighbours(self, earth):
        self.linked = None                                                      # Closest sat linked
        self.upper  = earth.LEO[self.in_plane].sats[self.i_in_plane-1]          # Previous sat in the same plane
        if self.i_in_plane < self.n_sat-1:
            self.lower = earth.LEO[self.in_plane].sats[self.i_in_plane+1]       # Following sat in the same plane
        else:
            self.lower = earth.LEO[self.in_plane].sats[0]                       # last satellite of the plane

    def rotate(self, delta_t, longitude, period):
        """
        Rotates the satellite by re-calculating the sperical coordinates, Cartesian coordinates, and longitude and
        latitude adjusted for the new longitude of the orbit, and fraction the elapsed time makes up of the orbit time
        of the satellite.
        """
        # Updating spherical coordinates upon rotation (these are phi, theta before inclination)
        self.phi = longitude
        self.theta = self.theta + 2*math.pi*delta_t/period
        self.theta = self.theta % (2*math.pi)

        # Calculating x,y,z coordinates with inclination
        self.x = self.r * (math.sin(self.theta)*math.cos(self.phi) - math.cos(self.theta)*math.sin(self.phi)*math.sin(self.inclination))
        self.y = self.r * (math.sin(self.theta)*math.sin(self.phi) + math.cos(self.theta)*math.cos(self.phi)*math.sin(self.inclination))
        self.z = self.r * math.cos(self.theta)*math.cos(self.inclination)
        self.polar_angle = self.theta  # Angle within orbital plane [radians]
        # updating latitude and longitude after rotation [degrees]
        self.latitude = math.asin(self.z/self.r)  # latitude corresponding to the satellite
        # longitude corresponding to satellite
        if self.x > 0:
            self.longitude = math.atan(self.y/self.x)
        elif self.x < 0 and self.y >= 0:
            self.longitude = math.pi + math.atan(self.y/self.x)
        elif self.x < 0 and self.y < 0:
            self.longitude = math.atan(self.y/self.x) - math.pi
        elif self.y > 0:
            self.longitude = math.pi/2
        elif self.y < 0:
            self.longitude = -math.pi/2
        else:
            self.longitude = 0


class edge:
    def  __init__(self, sati, satj, slant_range, dji, dij, shannonRate):
        '''
        dji && dij are deprecated. We do not use them anymore to decide which neighbour is at the right or left direction. We are using their coordinates.
        '''
        self.i = sati   # sati ID
        self.j = satj   # satj ID
        self.slant_range = slant_range  # distance between both sats
        self.dji = dji  # direction from sati to satj
        self.dij = dij  # direction from sati to satj
        self.shannonRate = shannonRate  # max dataRate between sat1 and satj

    def  __repr__(self):
        return '\n node i: {}, node j: {}, slant_range: {}, shannonRate: {}'.format(
    self.i,
    self.j,
    self.slant_range,
    self.shannonRate)

    def __cmp__(self, other):
        if hasattr(other, 'slant_range'):    # returns true if has 'weight' attribute
            return self.slant_range.__cmp__(other.slant_range)


class DataBlock:
    """
    Class for outgoing block of data from the gateways.
    Instead of simulating the individual data packets from each user, data is gathered at the GTs in blocks - one for
    each destination GT. Once a block is filled with data it is sent as one unit to the destination GT.
    """

    def __init__(self, source, destination, ID, creationTime):
        self.size = blockSize  # size in bits
        self.destination = destination
        self.source = source
        self.ID = ID            # a string which holds the source id, destination id, and index of the block, e.g. "1_2_12"
        self.timeAtFull = None  # the simulation time at which the block was full and was ready to be sent.
        self.creationTime = creationTime  # the simulation time at which the block was created.
        self.timeAtFirstTransmission = None  # the simulation time at which the block left the GT.
        self.checkPoints = []   # list of simulation reception times at node with the first entry being the reception time at first sat - can be expanded to include the sat IDs at each checkpoint
        self.checkPointsSend = []   # list of times after the block was sent at each node
        self.path = []
        self.queueLatency = (None, None) # total time acumulated in the queues
        self.txLatency = 0      # total transmission time
        self.propLatency = 0    # total propagation latency
        self.totLatency = 0     # total latency
        self.isNewPath = False
        self.oldPath = []
        self.newPath = []
        self.QPath   = []
        self.queue   = []
        self.queueTime= []
        self.oldState  = None
        self.oldAction = None
        # self.oldReward = None

    def getQueueTime(self):
        '''
        The queue latency is computed in two steps:
        First one: time when the block is sent for the first time - time when the the block is created
        Rest of the steps: sum(checkpoint (Arrival time at node) - checkpointsSend (send time at previous node))
        '''
        queueLatency = [0, []]
        queueLatency[0] += self.timeAtFirstTransmission - self.creationTime        # ANCHOR queue first step
        queueLatency[1].append(self.timeAtFirstTransmission - self.creationTime)
        for arrived, sendReady in zip(self.checkPoints, self.checkPointsSend):  # rest of the steps
            queueLatency[0] += sendReady - arrived
            queueLatency[1].append(sendReady - arrived)

        self.queueLatency = queueLatency
        return queueLatency

    def getTotalTransmissionTime(self):
        totalTime = 0
        if len(self.checkPoints) == 1:
            return self.checkPoints[0] - self.timeAtFirstTransmission

        lastTime = self.creationTime
        for time in self.checkPoints:
            totalTime += time - lastTime
            lastTime = time
        # ANCHOR KPI: totLatency
        self.totLatency = totalTime
        return totalTime

    def __repr__(self):
        return'ID = {}\n Source:\n {}\n Destination:\n {}\nTotal latency: {}'.format(
            self.ID,
            self.source,
            self.destination,
            self.totLatency
        )


# @profile
class Gateway:
    """
    Class for the gateways (or concentrators). Each gateway will exist as an instance of this class
    which means that each ground station will have separate processes filling and sending blocks to all other GTs.
    """
    def __init__(self, name: str, ID: int, latitude: float, longitude: float, totalX: int, totalY: int, totalGTs, env, totalLocations, earth):
        self.name   = name
        self.ID     = ID
        self.earth  = earth
        self.latitude   = latitude  # number is already in degrees
        self.longitude  = longitude  # number is already in degrees

        # using the formulas from the set_window() function in the Earth class to the location in terms of cell grid.
        self.gridLocationX = int((0.5 + longitude / 360) * totalX)
        self.gridLocationY = int((0.5 - latitude / 180) * totalY)
        self.cellsInRange = []  # format: [ [(lat,long), userCount, distance], [..], .. ]
        self.totalGTs = totalGTs  # number of GTs including itself
        self.totalLocations = totalLocations # number of possible GTs
        self.totalAvgFlow = None  # total combined average flow from all users in bits per second
        self.totalX = totalX
        self.totalY = totalY

        # cartesian coordinates
        self.polar_angle = (math.pi / 2 - math.radians(self.latitude) + 2 * math.pi) % (2 * math.pi)  # Polar angle in radians
        self.x = Re * math.cos(math.radians(self.longitude)) * math.sin(self.polar_angle)
        self.y = Re * math.sin(math.radians(self.longitude)) * math.sin(self.polar_angle)
        self.z = Re * math.cos(self.polar_angle)

        # satellite linking structure
        self.satsOrdered = []
        self.satIndex = 0
        self.linkedSat = (None, None)  # (distance, sat)
        self.graph = nx.Graph()

        # simpy attributes
        self.env = env  # simulation environment
        self.datBlocks = []  # list of outgoing data blocks - one for each destination GT
        self.fillBlocks = []  # list of simpy processes which fills up the data blocks
        self.sendBlocks = env.process(self.sendBlock())  # simpy process which sends the data blocks
        self.sendBuffer = ([env.event()], [])  # queue of blocks that are ready to be sent
        self.paths = {}  # dictionary for destination: path pairs

        # comm attributes
        self.dataRate = None
        self.gs2ngeo = RFlink(
            frequency=30e9,
            bandwidth=500e6,
            maxPtx=20,
            aDiameterTx=0.33,
            aDiameterRx=0.26,
            pointingLoss=0.3,
            noiseFigure=2,
            noiseTemperature=290,
            min_rate=10e3
        )

    def makeFillBlockProcesses(self, GTs):
        """
        Creates the processes for filling the data blocks and adding them to the send-buffer. A separate process for
        each destination gateway is created.
        """

        self.totalGTs = len(GTs)

        for gt in GTs:
            if gt != self:
                # add a process for each destination which runs the function 'fillBlock'
                self.fillBlocks.append(self.env.process(self.fillBlock(gt)))

    def fillBlock(self, destination):
        """
        Simpy process function:

        Creates a block headed for a given destination, finds the time for a block to be full and adds the block to the
        send-buffer after the calculated time.

        A separate process for each destination gateway will be running this function.
        """
        index = 0
        unavailableDestinationBuffer = []

        while True:
            try:
                # create a new block to be filled
                block = DataBlock(self, destination, str(self.ID) + "_" + str(destination.ID) + "_" + str(index), self.env.now)

                timeToFull = self.timeToFullBlock(block)  # calculate time to fill block

                yield self.env.timeout(timeToFull)  # wait until block is full

                if block.destination.linkedSat[0] is None:
                    unavailableDestinationBuffer.append(block)
                else:
                    while unavailableDestinationBuffer: # empty buffer before adding new block
                        if not self.sendBuffer[0][0].triggered:
                            self.sendBuffer[0][0].succeed()
                            self.sendBuffer[1].append(unavailableDestinationBuffer[0])
                            unavailableDestinationBuffer.pop(0)
                        else:
                            newEvent = self.env.event().succeed()
                            self.sendBuffer[0].append(newEvent)
                            self.sendBuffer[1].append(unavailableDestinationBuffer[0])
                            unavailableDestinationBuffer.pop(0)

                    block.path = self.paths[destination.name]

                    if self.earth.pathParam == 'Q-Learning' or self.earth.pathParam == 'Deep Q-Learning':
                        block.QPath = [block.path[0], block.path[1], block.path[len(block.path)-1]]
                        # We add a Qpath field for the Q-Learning case. Only source and destination will be added
                        # after that, every hop will be added at the second last position.

                    if not block.path:
                        print(self.name, destination.name)
                        exit()
                    block.timeAtFull = self.env.now
                    createdBlocks.append(block)
                    # add block to send-buffer
                    if not self.sendBuffer[0][0].triggered:
                        self.sendBuffer[0][0].succeed()
                        self.sendBuffer[1].append(block)
                    else:
                        newEvent = self.env.event().succeed()
                        self.sendBuffer[0].append(newEvent)
                        self.sendBuffer[1].append(block)
                    index += 1
            except simpy.Interrupt:
                print(f'Simpy interrupt at filling block at gateway{self.name}')
                break

    def sendBlock(self):
        """
        Simpy process function:

        Sends data blocks that are filled and added to the send-buffer which is a list of events and data blocks. The
        function monitors the send-buffer, and when the buffer contains one or more triggered events, the function will
        calculate the time it will take to send the block (yet to be implemented), and trigger an event which notifies
        a separate process that a block has been sent (yet to be implemented).

        After a block is sent, the function will send the next, if any more blocks are ready to be sent.

        (While it is assumed that if a buffer is full and ready to be sent it will always be at the first index,
        the method simpy.AnyOf is used. The end result is the same and this method is simple to implement.
        Furthermore, it allows for handling of such errors where a later index is ready but the first is not.
        this case is, however, not handled.)

        Since there is only one link on the GT for sending, there will only be one process running this method.
        """
        while True:
            yield self.sendBuffer[0][0]     # event 0 of block 0

            # wait until a satellite is linked
            while self.linkedSat[0] is None:
                yield self.env.timeout(0.1)

            # calculate propagation time and transmission time
            propTime = self.timeToSend(self.linkedSat)
            timeToSend = blockSize/self.dataRate

            self.sendBuffer[1][0].timeAtFirstTransmission = self.env.now
            yield self.env.timeout(timeToSend)
            # ANCHOR KPI: txLatency send block from GT
            self.sendBuffer[1][0].txLatency += timeToSend

            if not self.sendBuffer[1][0].path:
                print(self.sendBuffer[1][0].source.name, self.sendBuffer[1][0].destination.name)
                exit()

            self.linkedSat[1].createReceiveBlockProcess(self.sendBuffer[1][0], propTime)

            # remove from own sendBuffer
            if len(self.sendBuffer[0]) == 1:
                self.sendBuffer[0].pop(0)
                self.sendBuffer[1].pop(0)
                self.sendBuffer[0].append(self.env.event())
            else:
                self.sendBuffer[0].pop(0)
                self.sendBuffer[1].pop(0)

    def timeToSend(self, linkedSat):
        distance = linkedSat[0]
        pTime = distance/Vc
        return pTime

    def createReceiveBlockProcess(self, block, propTime):
        """
        Function which starts a receiveBlock process upon receiving a block from a transmitter.
        Adds the propagation time to the block attribute
        """

        process = self.env.process(self.receiveBlock(block, propTime))

    def receiveBlock(self, block, propTime):
        """
        Simpy process function:

        This function is used to handle the propagation delay of data blocks. This is done simply by waiting the time
        of the propagation delay. As a GT will always be the last step in a block's path, there is no need to send the
        block further. After the propagation delay, the block is simply added to a list of finished blocks so the KPIs
        can be tracked at the end of the simulation.

        While the transmission delay is handled at the transmitter, the transmitter cannot also wait for the propagation
        delay, otherwise the send-buffer might be overfilled.
        """
        # wait for block to fully propagate
        yield self.env.timeout(propTime)
        # ANCHOR KPI: propLatency send block from GT
        block.propLatency += propTime

        block.checkPoints.append(self.env.now)

        receivedDataBlocks.append(block)

    def cellDistance(self, cell) -> float:
        """
        Calculates the distance to the specified cell (assumed the center of the cell).
        Calculation is based on the geopy package which uses the 'WGS-84' model for earth shape.
        """
        cellCoord = (math.degrees(cell.latitude), math.degrees(cell.longitude))  # cell lat and long is saved in a format which is not degrees
        gTCoord = (self.latitude, self.longitude)

        return geopy.distance.geodesic(cellCoord,gTCoord).km

    def distance_GSL(self, satellite):
        """
        Distance between GT and satellite is calculated using the distance formula based on the cartesian coordinates
        in 3D space.
        """

        satCoords = [satellite.x, satellite.y, satellite.z]
        GTCoords = [self.x, self.y, self.z]

        distance = math.dist(satCoords, GTCoords)
        return distance

    def adjustDataRate(self):

        speff_thresholds = np.array(
            [0, 0.434841, 0.490243, 0.567805, 0.656448, 0.789412, 0.889135, 0.988858, 1.088581, 1.188304, 1.322253,
             1.487473, 1.587196, 1.647211, 1.713601, 1.779991, 1.972253, 2.10485, 2.193247, 2.370043, 2.458441,
             2.524739, 2.635236, 2.637201, 2.745734, 2.856231, 2.966728, 3.077225, 3.165623, 3.289502, 3.300184,
             3.510192, 3.620536, 3.703295, 3.841226, 3.951571, 4.206428, 4.338659, 4.603122, 4.735354, 4.933701,
             5.06569, 5.241514, 5.417338, 5.593162, 5.768987, 5.900855])
        lin_thresholds = np.array(
            [1e-10, 0.5188000389, 0.5821032178, 0.6266138647, 0.751622894, 0.9332543008, 1.051961874, 1.258925412,
             1.396368361, 1.671090614, 2.041737945, 2.529297996, 2.937649652, 2.971666032, 3.25836701, 3.548133892,
             3.953666201, 4.518559444, 4.83058802, 5.508076964, 6.45654229, 6.886522963, 6.966265141, 7.888601176,
             8.452788452, 9.354056741, 10.49542429, 11.61448614, 12.67651866, 12.88249552, 14.48771854, 14.96235656,
             16.48162392, 18.74994508, 20.18366364, 23.1206479, 25.00345362, 30.26913428, 35.2370871, 38.63669771,
             45.18559444, 49.88844875, 52.96634439, 64.5654229, 72.27698036, 76.55966069, 90.57326009])
        db_thresholds = np.array(
            [-100.00000, -2.85000, -2.35000, -2.03000, -1.24000, -0.30000, 0.22000, 1.00000, 1.45000, 2.23000, 3.10000,
             4.03000, 4.68000, 4.73000, 5.13000, 5.50000, 5.97000, 6.55000, 6.84000, 7.41000, 8.10000, 8.38000, 8.43000,
             8.97000, 9.27000, 9.71000, 10.21000, 10.65000, 11.03000, 11.10000, 11.61000, 11.75000, 12.17000, 12.73000,
             13.05000, 13.64000, 13.98000, 14.81000, 15.47000, 15.87000, 16.55000, 16.98000, 17.24000, 18.10000,
             18.59000, 18.84000, 19.57000])

        pathLoss = 10*np.log10((4*math.pi*self.linkedSat[0]*self.gs2ngeo.f/Vc)**2)
        snr = 10**((self.gs2ngeo.maxPtx_db + self.gs2ngeo.G - pathLoss - self.gs2ngeo.No)/10)
        shannonRate = self.gs2ngeo.B*np.log2(1+snr)

        feasible_speffs = speff_thresholds[np.nonzero(lin_thresholds <= snr)]
        speff = self.gs2ngeo.B*feasible_speffs[-1]

        self.dataRate = speff

    def orderSatsByDist(self, constellation):
        """
        Calculates the distance from the GT to all satellites and saves a sorted (least to greatest distance) list of
        all the satellites that are within range of the GT.
        """
        sats = []
        index = 0
        for orbitalPlane in constellation:
            for sat in orbitalPlane.sats:
                d_GSL = self.distance_GSL(sat)
                # ensure that the satellite is within range
                if d_GSL <= sat.maxSlantRange:
                    sats.append((d_GSL, sat, [index]))
                index += 1
        sats.sort()
        self.satsOrdered = sats

    def addRefOnSat(self):
        """
        Adds a reference of the GT on a satellite based on the local list of satellites that are within range of the GT.
        This function is used in the greedy version of the 'linkSats2GTs()' method in the Earth class.
        The function uses a local indexing number to choose which satellite to add a reference to. If the satellite
        already has a reference, the GT checks if it is closer than the existing reference. If it is closer, it
        overwrites the reference and forces the other GT to add a reference to the next satellite it its own list.
        """
        if self.satIndex >= len(self.satsOrdered):
            self.linkedSat = (None, None)
            print("No satellite for GT {}".format(self.name))
            return

        # check if satellite has reference
        if self.satsOrdered[self.satIndex][1].linkedGT is None:
            # add self as reference on satellite
            self.satsOrdered[self.satIndex][1].linkedGT = self
            self.satsOrdered[self.satIndex][1].GTDist = self.satsOrdered[self.satIndex][0]

        # check if satellites reference is further away than this GT
        elif self.satsOrdered[self.satIndex][1].GTDist < self.satsOrdered[self.satIndex][0]:
            # force other GT to increment satIndex and check next satellite in its local ordered list
            self.satsOrdered[self.satIndex][1].linkedGT.satIndex += 1
            self.satsOrdered[self.satIndex][1].linkedGT.addRefOnSat()

            # add self as reference on satellite
            self.satsOrdered[self.satIndex][1].linkedGT = self
            self.satsOrdered[self.satIndex][1].GTDist = self.satsOrdered[self.satIndex][0]
        else:
            self.satIndex += 1
            if self.satIndex == len(self.satsOrdered):
                self.linkedSat = (None, None)
                print("No satellite for GT {}".format(self.name))
                return

            self.addRefOnSat()

    def link2Sat(self, dist, sat):
        """
        Links the GT to the satellite chosen in the 'linkSats2GTs()' method in the Earth class and makes sure that the
        data rate for the RFlink to the satellite is updated.
        """
        self.linkedSat = (dist, sat)
        sat.linkedGT = self
        sat.GTDist = dist
        self.adjustDataRate()

    def addCell(self, cellInfo):
        """
        Links a cell to the GT by adding the relevant information of the cell to the local list "cellsInRange".
        """
        self.cellsInRange.append(cellInfo)

    def removeCell(self, cell):
        """
        Unused function
        """
        for i, cellInfo in enumerate(self.cellsInRange):
            if cell.latitude == cellInfo[0][0] and cell.longitude == cellInfo[0][1]:
                cellInfo.pop(i)
                return True
        return False

    def findCellsWithinRange(self, earth, maxDistance):
        """
        This function finds the cells that are within the coverage area of the gateway instance. The cells are
        found by checking cells one at a time from the location of the gateway moving outward in a circle until
        the edge of the circle around the terminal exclusively consists of cells that border cells which are outside the
        coverage area. This is an optimized way of finding the cells within the coverage area, as only a limited number
        of cells outside the coverage is checked.

        The size of the area that is checked for is based on the parameter 'maxDistance' which can be seen as the radius
        of the coverage area in kilometers.

        The function will not "link" the cells and the gateway. Instead, it will only add a reference in the
        cells to the closest GT. As a result, all GTs must run this function before any linking is performed. The
        linking is done in the function: "linkCells2GTs()", in the Earth class, which also runs this function. This is
        done to handle cases where the coverage areas of two or more GTs are overlapping and the cells must only link to
        one of the GTs.

        The information added to the "cellsWithinRange" list is used for generating flows from the cells to each GT.
        """

        # Up right:
        isWithinRangeX = True
        x = self.gridLocationX
        while isWithinRangeX:
            y = self.gridLocationY
            isWithinRangeY = True
            if x == earth.total_x: # "roll over" to opposite side of grid.
                x = 0
            cell = earth.cells[x][y]
            distance = self.cellDistance(cell)
            if distance > maxDistance:
                isWithinRangeY = False
                isWithinRangeX = False
            while isWithinRangeY:
                if y == -1:  # "roll over" to opposite side of grid.
                    y = earth.total_y - 1
                cell = earth.cells[x][y]
                distance = self.cellDistance(cell)
                if distance > maxDistance:
                    isWithinRangeY = False
                else:
                    # check if any GT has been added to cell, and if any has check if current GT is closer.
                    if cell.gateway is None or cell.gateway is not None and distance < cell.gateway[1]:
                        # No GT is added to cell or current GT is closer - add current GT.
                        cell.gateway = (self, distance)
                y -= 1  # the y-axis is flipped in the cell grid.
            x += 1

        # Down right:
        isWithinRangeX = True
        x = self.gridLocationX
        while isWithinRangeX:
            y = self.gridLocationY + 1
            isWithinRangeY = True
            if x == earth.total_x:  # "roll over" to opposite side of grid.
                x = 0
            cell = earth.cells[x][y]
            distance = self.cellDistance(cell)
            if distance > maxDistance:
                isWithinRangeY = False
                isWithinRangeX = False
            while isWithinRangeY:
                if y == earth.total_y:  # "roll over" to opposite side of grid.
                    y = 0
                cell = earth.cells[x][y]
                distance = self.cellDistance(cell)
                if distance > maxDistance:
                    isWithinRangeY = False
                else:
                    # check if any GT has been added to cell, and if any has check if current GT is closer.
                    if cell.gateway is None or cell.gateway is not None and distance < cell.gateway[1]:
                        # No GT is added to cell or current GT is closer - add current GT.
                        cell.gateway = (self, distance)
                y += 1  # the y-axis is flipped in the cell grid.
            x += 1

        # up left:
        isWithinRangeX = True
        x = self.gridLocationX - 1
        while isWithinRangeX:
            y = self.gridLocationY
            isWithinRangeY = True
            if x == -1:  # "roll over" to opposite side of grid.
                x = earth.total_x - 1
            cell = earth.cells[x][y]
            distance = self.cellDistance(cell)
            if distance > maxDistance:
                isWithinRangeY = False
                isWithinRangeX = False
            while isWithinRangeY:
                if y == -1:  # "roll over" to opposite side of grid.
                    y = earth.total_y - 1
                cell = earth.cells[x][y]
                distance = self.cellDistance(cell)
                if distance > maxDistance:
                    isWithinRangeY = False
                else:
                    # check if any GT has been added to cell, and if any has check if current GT is closer.
                    if cell.gateway is None or cell.gateway is not None and distance < cell.gateway[1]:
                        # No GT is added to cell or current GT is closer - add current GT.
                        cell.gateway = (self, distance)
                y -= 1  # the y-axis is flipped in the cell grid.
            x -= 1

        # down left:
        isWithinRangeX = True
        x = self.gridLocationX - 1
        while isWithinRangeX:
            y = self.gridLocationY + 1
            isWithinRangeY = True
            if x == -1:  # "roll over" to opposite side of grid.
                x = earth
            cell = earth.cells[x][y]
            distance = self.cellDistance(cell)
            if distance > maxDistance:
                isWithinRangeY = False
                isWithinRangeX = False
            while isWithinRangeY:
                if y == -1:  # "roll over" to opposite side of grid.
                    y = earth.total_y - 1
                cell = earth.cells[x][y]
                distance = self.cellDistance(cell)
                if distance > maxDistance:
                    isWithinRangeY = False
                else:
                    # check if any GT has been added to cell, and if any has check if current GT is closer.
                    if cell.gateway is None or cell.gateway is not None and distance < cell.gateway[1]:
                        # No GT is added to cell or current GT is closer - add current GT.
                        cell.gateway = (self, distance)
                y += 1  # the y-axis is flipped in the cell grid.
            x -= 1

    def timeToFullBlock(self, block):
        """
        Calculates the average time it will take to fill up a data block and returns the actual time based on a
        random variable following an exponential distribution.
        Different from the non reinforcement version of the simulator, this does not include different methods for
        setting the fractions of the data generation to each destination gateway.
        """

        # split the traffic evenly among the active gateways while keeping the fraction to each gateway the same
        # regardless of number of active gateways
        flow = self.totalAvgFlow / (len(self.totalLocations) - 1)

        avgTime = block.size / flow  # the average time to fill the buffer in seconds

        time = np.random.exponential(scale=avgTime) # the actual time to fill the buffer after adjustment by exp dist.

        return time

    def getTotalFlow(self, avgFlowPerUser, distanceFunc, maxDistance, capacity = None, fraction = 1.0):
        """
        This function is used as a precursor for the 'timeToFillBlock' method. Based on one of two distance functions
        this function finds the combined average flow from the combined users within the ground coverage area of the GT.

        Calculates the average combined flow from all cells scaling with distance in one of two ways:
            For the step function this means that it essentially just counts the number of users from the local list and
            multiplies with the flowPerUser value.

            For the slope it means that the slope is found using the flowPerUser and maxDistance as the gradient where
            the function gives 0 at the maximum distance.

            If this logic should be changed, it is important that it is done so in accordance with the
            "findCellsWithinRange" method.
        """
        if balancedFlow:
            self.totalAvgFlow = totalFlow
        else:
            totalAvgFlow = 0
            avgFlowPerUser =  avUserLoad

            if distanceFunc == "Step":
                for cell in self.cellsInRange:
                    totalAvgFlow += cell[1] * avgFlowPerUser

            elif distanceFunc == "Slope":
                gradient = (0-avgFlowPerUser)/(maxDistance-0)
                for cell in self.cellsInRange:
                    totalAvgFlow += (gradient * cell[2] + avgFlowPerUser) * cell[1]

            else:
                print("Error, distance function not recognized. Provided function = {}. Allowed functions: {} or {}".format(
                    distanceFunc,
                    "Step",
                    "slope"))
                exit()

            if self.linkedSat[0] is None:
                self.dataRate = self.gs2ngeo.min_rate

            if not capacity:
                capacity = self.dataRate

            if totalAvgFlow < capacity * fraction:
                self.totalAvgFlow = totalAvgFlow
            else:
                self.totalAvgFlow = capacity * fraction
                
        print(self.name + ': ' + str(self.totalAvgFlow/1000000000))

    def __eq__(self, other):
        if self.latitude == other.latitude and self.longitude == other.longitude:
            return True
        else:
            return False

    def __repr__(self):
        return 'Location = {}\n Longitude = {}\n Latitude = {}\n pos x= {}, pos y= {}, pos z= {}'.format(
            self.name,
            self.longitude,
            self.latitude,
            self.x,
            self.y,
            self.z)


# A single cell on earth
class Cell:
    def __init__(self, total_x, total_y, cell_x, cell_y, users, Re=6378e3, f=20e9, bw=200e6, noise_power=1 / (1e11)):
        # X and Y coordinates of the cell on the dataset map
        self.map_x = cell_x
        self.map_y = cell_y
        # Latitude and longitude of the cell as per dataset map
        self.latitude = math.pi * (0.5 - cell_y / total_y)
        self.longitude = (cell_x / total_x - 0.5) * 2 * math.pi
        if self.latitude < -5 or self.longitude < -5:
            print("less than 0")
            print(self.longitude, self.latitude)
            print(cell_x, cell_y)
            # exit()
        # Actual area the cell covers on earth (scaled for)
        self.area = 4 * math.pi * Re * Re * math.cos(self.latitude) / (total_x * total_y)
        # X,Y,Z coordinates to the center of the cell (assumed)
        self.x = Re * math.cos(self.latitude) * math.cos(self.longitude)
        self.y = Re * math.cos(self.latitude) * math.sin(self.longitude)
        self.z = Re * math.sin(self.latitude)

        self.users = users  # Population in the cell
        self.f = f  # Frequency used by the cell
        self.bw = bw  # Bandwidth used for the cell
        self.noise_power = noise_power  # Noise power for the cell
        self.rejected = True  # Usefulfor applications process to show if the cell is rejected or accepted
        self.gateway = None  # (groundstation, distance)

    def __repr__(self):
        return 'Users = {}\n area = {} km^2\n longitude = {} deg\n latitude = {} deg\n pos x = {}\n pos y = {}\n pos ' \
               'z = {}\n x position on map = {}\n y position on map = {}'.format(
                self.users,
                '%.2f' % (self.area / 1e6),
                '%.2f' % math.degrees(self.longitude),
                '%.2f' % math.degrees(self.latitude),
                '%.2f' % self.x,
                '%.2f' % self.y,
                '%.2f' % self.z,
                '%.2f' % self.map_x,
                '%.2f' % self.map_y)

    def setGT(self, gateways, maxDistance = 60):
        """
        Finds the closest gateway and updates the internal attribute 'self.gateway' as a tuple:
        (Gateway, distance to terminal). If the distance to the closest gateway is less than some maximum
        distance, the cell information is added to the gateway.
        """
        closestGT = (gateways[0], gateways[0].cellDistance(self))
        for gateway in gateways[1:]:
            distanceToGT = gateway.cellDistance(self)
            if distanceToGT < closestGT[1]:
                closestGT = (gateway, distanceToGT)
        self.gateway = closestGT

        if closestGT[1] <= maxDistance:
            closestGT[0].addCell([(math.degrees(self.latitude), math.degrees(self.longitude)), self.users, closestGT[1]])
        else:
            self.users = 0
        return closestGT


# Earth consisting of cells
# @profile
class Earth:
    def __init__(self, env, img_path, gt_path, constellation, inputParams, deltaT, totalLocations, getRates = False, window=None, outputPath='/'):
        # Input the population count data
        # img_path = 'Population Map/gpw_v4_population_count_rev11_2020_15_min.tif'
        self.outputPath = outputPath
        self.printPaths = printPath
        self.lostBlocks = 0
        self.queues = []
        self.loss   = []
        self.lossAv = []
        self.DDQNA  = None
        self.step   = 0
        self.epsilon=[]

        pop_count_data = Image.open(img_path)

        pop_count = np.array(pop_count_data)
        pop_count[pop_count < 0] = 0  # ensure there are no negative values

        # total image sizes
        [self.total_x, self.total_y] = pop_count_data.size

        self.total_cells = self.total_x * self.total_y

        # List of all cells stored in a 2d array as per the order in dataset
        self.cells = []
        for i in range(self.total_x):
            self.cells.append([])
            for j in range(self.total_y):
                self.cells[i].append(Cell(self.total_x, self.total_y, i, j, pop_count[j][i]))

        # window is a list with the coordinate bounds of our window of interest
        # format for window = [western longitude, eastern longitude, southern latitude, northern latitude]
        if window is not None:  # if window provided
            # latitude, longitude bounds:
            self.lati = [window[2], window[3]]
            self.longi = [window[0], window[1]]
            # dataset pixel bounds:
            self.windowx = (
            (int)((0.5 + window[0] / 360) * self.total_x), (int)((0.5 + window[1] / 360) * self.total_x))
            self.windowy = (
            (int)((0.5 - window[3] / 180) * self.total_y), (int)((0.5 - window[2] / 180) * self.total_y))
        else:  # set window size as entire world if no window provided
            self.lati = [-90, 90]
            self.longi = [-179, 180]
            self.windowx = (0, self.total_x)
            self.windowy = (0, self.total_y)

        # import gateways from .csv
        self.gateways = []

        gateways = pd.read_csv(gt_path)

        length = 0
        for i, location in enumerate(gateways['Location']):
            for name in inputParams['Locations']:
                if name in location.split(","):
                    length += 1

        if inputParams['Locations'][0] != 'All':
            for i, location in enumerate(gateways['Location']):
                for name in inputParams['Locations']:
                    if name in location.split(","):
                        lName = gateways['Location'][i]
                        gtLati = gateways['Latitude'][i]
                        gtLongi = gateways['Longitude'][i]
                        self.gateways.append(Gateway(lName, i, gtLati, gtLongi, self.total_x, self.total_y,
                                                                   length, env, totalLocations, self))
                        break
        else:
            for i in range(len(gateways['Latitude'])):
                name = gateways['Location'][i]
                gtLati = gateways['Latitude'][i]
                gtLongi = gateways['Longitude'][i]
                self.gateways.append(Gateway(name, i, gtLati, gtLongi, self.total_x, self.total_y,
                                                           len(gateways['Latitude']), env, totalLocations, self))

        self.pathParam = pathing

        # create data Blocks on all GTs.
        if not getRates:
            for gt in self.gateways:
                gt.makeFillBlockProcesses(self.gateways)

        # create constellation of satellites
        self.LEO = create_Constellation(constellation, env, self)

        # Simpy process for handling moving the constellation and the satellites within the constellation
        self.moveConstellation = env.process(self.moveConstellation(env, deltaT, getRates))

    def set_window(self, window):  # function to change/set window for the earth
        """
        Unused function
        """
        self.lati = [window[2], window[3]]
        self.longi = [window[0], window[1]]
        self.windowx = ((int)((0.5 + window[0] / 360) * self.total_x), (int)((0.5 + window[1] / 360) * self.total_x))
        self.windowy = ((int)((0.5 - window[3] / 180) * self.total_y), (int)((0.5 - window[2] / 180) * self.total_y))

    def linkCells2GTs(self, distance):
        """
        Finds the cells that are within the coverage areas of all GTs and links them ensuring that a cell only links to
        a single GT.
        """
        start = time.time()

        # Find cells that are within range of all GTs
        for i, gt in enumerate(self.gateways):
            print("Finding cells within coverage area of GT {} of {}".format(i+1, len(self.gateways)), end='\r')
            gt.findCellsWithinRange(self, distance)
        print('\r')
        print("Time taken to find cells that are within range of all GTs: {} seconds".format(time.time() - start))

        start = time.time()

        # Add reference for cells to the GT they are closest to
        for cells in self.cells:
            for cell in cells:
                if cell.gateway is not None:
                    cell.gateway[0].addCell([(math.degrees(cell.latitude),
                                                     math.degrees(cell.longitude)),
                                                    cell.users,
                                                    cell.gateway[1]])

        print("Time taken to add cell information to all GTs: {} seconds".format(time.time() - start))
        print()

    def linkSats2GTs(self, method):
        """
        Links GTs to satellites. One satellite is only allowed to link to one GT.
        """
        sats = []
        for orbit in self.LEO:
            for sat in orbit.sats:
                sat.linkedGT = None
                sat.GTDist = None
                sats.append(sat)

        if method == "Greedy":
            for GT in self.gateways:
                GT.orderSatsByDist(self.LEO)
                GT.addRefOnSat()

            for orbit in self.LEO:
                for sat in orbit.sats:
                    if sat.linkedGT is not None:
                        sat.linkedGT.link2Sat(sat.GTDist, sat)
        elif method == "Optimize":
            # make cost matrix
            SxGT = np.array([[99999 for _ in range(len(sats))] for _ in range(len(self.gateways))])
            for i, GT in enumerate(self.gateways):
                GT.orderSatsByDist(self.LEO)
                for val, entry in enumerate(GT.satsOrdered):
                    SxGT[i][entry[2][0]] = val

            # find assignment of GSL which minimizes the cost from the cost matrix
            rowInd, colInd = linear_sum_assignment(SxGT)

            # link satellites and GTs
            for i, GT in enumerate(self.gateways):
                if SxGT[rowInd[i]][colInd[i]] < len(GT.satsOrdered):
                    sat = GT.satsOrdered[SxGT[rowInd[i]][colInd[i]]]
                    GT.link2Sat(sat[0], sat[1])
                else:
                    GT.linkedSat = (None, None)
                    print("no satellite for GT {}".format(GT.name))

    def getCellUsers(self):
        """
        Used for plotting the population map.
        """
        temp = []
        for i, cellList in enumerate(self.cells):
            temp.append([])
            for cell in cellList:
                temp[i].append(cell.users)
        return temp

    def updateSatelliteProcessesSimpler(self, graph):
        """

        Function from the non-reinforcement implementation. However, due to the paths not existing between transmitter
        and destination gateways (they get created as the blocks travel through the constellation), this version does
        work with Q-Learning and Deep-Learning.

        Can be used for a simpler version of updating the processes on satellites. However, it does not take into
        account that some processes may be able to continue without being stopped. Stopping the processes may lose
        time of the transmission of a block.

        Function which ensures all processes on all satellites are updated after constellation movement. This is done in
        several steps:
            - All blocks waiting to be sent or currently being sent has their paths updated.
            - All processes are stopped and remade according to current links - all transmission progress is lost on
            blocks currently being transmitted.
            - All buffers are emptied and blocks are redistributed to new buffers according to the blocks' arrival time
            at the satellite.
        """

        # update ISL references in all satellites, adjust data rate to GTs and ensure send-processes are correct
        sats = []
        for plane in self.LEO:
            for sat1 in plane.sats:
                sats.append(sat1)
        for plane in self.LEO:
            for sat in plane.sats:

                # remake path for all blocks
                for buffer in sat.sendBufferSatsIntra:
                    for block in buffer[1]:
                        destination = block.destination.name
                        newPath = getShortestPath(sat.ID, destination, self.pathParam, graph)
                        path = None
                        # splice old and new path
                        for i, step in enumerate(block.path):
                            if step[0] == sat.ID:
                                path = block.path[:i] + newPath
                                break
                        if path is None:
                            print("no path to sat:")
                            print(block)
                            exit()
                        block.path = path
                for buffer in sat.sendBufferSatsInter:
                    for block in buffer[1]:
                        destination = block.destination.name
                        newPath = getShortestPath(sat.ID, destination, self.pathParam, graph)
                        path = None
                        # splice old and new path
                        for i, step in enumerate(block.path):
                            if step[0] == sat.ID:
                                path = block.path[:i] + newPath
                                break
                        if path is None:
                            print("no path to sat:")
                            print(block)
                            exit()
                        block.path = path
                for block in sat.sendBufferGT[1]:
                    destination = block.destination.name
                    newPath = getShortestPath(sat.ID, destination, self.pathParam, graph)
                    path = None
                    # splice old and new path
                    for i, step in enumerate(block.path):
                        if step[0] == sat.ID:
                            path = block.path[:i] + newPath
                            break
                    if path is None:
                        print("no path to GT:")
                        print(block)
                        exit()
                    block.path = path
                for block in sat.tempBlocks:
                    destination = block.destination.name
                    newPath = getShortestPath(sat.ID, destination, self.pathParam, graph)
                    path = None
                    # splice old and new path
                    for i, step in enumerate(block.path):
                        if step[0] == sat.ID:
                            path = block.path[:i] + newPath
                            break
                    if path is None:
                        print("no path from Temp:")
                        print(block)
                        exit()
                    block.path = path

                # find neighboring satellites
                neighbors = list(nx.neighbors(graph, sat.ID))
                itt = 0
                neighborSats = []
                for sat2 in sats:
                    if sat2.ID in neighbors:
                        dataRate = nx.path_weight(graph, [sat2.ID, sat.ID], "dataRateOG")
                        distance = nx.path_weight(graph, [sat2.ID, sat.ID], "slant_range")
                        neighborSats.append((distance, sat2, dataRate))
                        itt += 1
                        if itt == len(neighbors):
                            break

                sat.intraSats = []
                sat.interSats = []

                # add new satellites as references
                for neighbor in neighborSats:
                    if neighbor[1].in_plane == sat.in_plane:
                        sat.intraSats.append(neighbor)
                    else:
                        sat.interSats.append(neighbor)

                # stop all processes
                for process in sat.sendBlocksSatsInter:
                    process.interrupt()
                for process in sat.sendBlocksSatsIntra:
                    process.interrupt()
                for process in sat.sendBlocksGT:
                    process.interrupt()
                sat.sendBlocksSatsIntra = []
                sat.sendBlocksSatsInter = []
                sat.sendBlocksGT = []

                # add all blocks to list and reset queues
                blocksToDistribute = []
                for buffer in sat.sendBufferSatsIntra:
                    for block in buffer[1]:
                        blocksToDistribute.append((block.checkPoints[-1], block))
                sat.sendBufferSatsIntra = []
                for buffer in sat.sendBufferSatsInter:
                    for block in buffer[1]:
                        blocksToDistribute.append((block.checkPoints[-1], block))
                sat.sendBufferSatsInter = []
                for block in sat.sendBufferGT[1]:
                    blocksToDistribute.append((block.checkPoints[-1], block))
                sat.sendBufferGT = ([sat.env.event()], [])

                # remake all processes
                if sat.linkedGT is not None:
                    sat.adjustDownRate()
                    # make a process for the GSL from sat to GT
                    sat.sendBlocksGT.append(sat.env.process(sat.sendBlock((sat.GTDist, sat.linkedGT), False)))

                for neighbor in sat.intraSats:
                    # make a send buffer for each ISL ([self.env.event()], [DataBlock(0, 0, "0", 0)], 0)
                    sat.sendBufferSatsIntra.append(([sat.env.event()], [], neighbor[1].ID))

                    # make a process for each ISL
                    sat.sendBlocksSatsIntra.append(sat.env.process(sat.sendBlock(neighbor, True, True)))

                for neighbor in sat.interSats:
                    # make a send buffer for each ISL ([self.env.event()], [DataBlock(0, 0, "0", 0)], 0)
                    sat.sendBufferSatsInter.append(([sat.env.event()], [], neighbor[1].ID))

                    # make a process for each ISL
                    sat.sendBlocksSatsInter.append(sat.env.process(sat.sendBlock(neighbor, True, False)))

                # sort blocks by arrival time at satellite
                blocksToDistribute.sort()
                # add blocks to the correct queues based on next step in their path
                # since the blocks list is sorted by arrival time, the order in the new queues is correct
                for block in blocksToDistribute:
                    # get this satellite's index in the blocks path
                    index = None
                    for i, step in enumerate(block[1].path):
                        if sat.ID == step[0]:
                            index = i

                    # check if next step in path is GT (last step in path)
                    if index == len(block[1].path) - 2:
                        # add block to GT send-buffer
                        if not sat.sendBufferGT[0][0].triggered:
                            sat.sendBufferGT[0][0].succeed()
                            sat.sendBufferGT[1].append(block[1])
                        else:
                            newEvent = sat.env.event().succeed()
                            sat.sendBufferGT[0].append(newEvent)
                            sat.sendBufferGT[1].append(block[1])
                    else:
                        # get ID of next sat and find if it is intra or inter
                        ID = None
                        isIntra = False
                        for neighborSat in sat.intraSats:
                            id = neighborSat[1].ID
                            if id == block[1].path[index + 1][0]:
                                ID = neighborSat[1].ID
                                isIntra = True
                        for neighborSat in sat.interSats:
                            id = neighborSat[1].ID
                            if id == block[1].path[index + 1][0]:
                                ID = neighborSat[1].ID

                        if ID is not None:
                            sendBuffer = None
                            # find send-buffer for the satellite
                            if isIntra:
                                for buffer in sat.sendBufferSatsIntra:
                                    if ID == buffer[2]:
                                        sendBuffer = buffer
                            else:
                                for buffer in sat.sendBufferSatsInter:
                                    if ID == buffer[2]:
                                        sendBuffer = buffer

                            # add block to buffer
                            if not sendBuffer[0][0].triggered:
                                sendBuffer[0][0].succeed()
                                sendBuffer[1].append(block[1])
                            else:
                                newEvent = sat.env.event().succeed()
                                sendBuffer[0].append(newEvent)
                                sendBuffer[1].append(block[1])
                        else:
                            print("buffer for next satellite in path could not be found")

    def updateSatelliteProcessesCorrect(self, graph):
        """

        Function from the non-reinforcement implementation. However, due to the paths not existing between transmitter
        and destination gateways (they get created as the blocks travel through the constellation), this version does
        work with Q-Learning and Deep-Learning.

        Function which ensures all processes on all satellites are updated after constellation movement. This is done in
        several steps:
            - All blocks waiting to be sent or currently being sent has their paths updated.
            - ISLs are updated with references to new inter-orbit satellites (intra-orbit links do not change).
                - This includes updating buffer if ISL is changed
                - It also includes remaking send-process if ISL is changed
                - Despite intra-orbit links not changing, blocks in an intra-orbit buffer may have to be moved.
            - GSL is updated:
                - Depending on new status - whether the satellite has a GSL or not - and past status - whether the
                satellite had a GSL or not - GSL buffer and process is handled accordingly.
            - All blocks not currently being transmitted to a satellite/GT, which is still present as a ISL or GSL, are
            redistributed to send-buffers according to their arrival time at the satellite.

        This function differentiates from the simple version by allowing continued operation of send-processes after
        constellation movement if the link is not broken.
        """
        sats = []
        for plane in self.LEO:
            for sat1 in plane.sats:
                sats.append(sat1)

        for plane in self.LEO:
            for sat in plane.sats:
                # remake path for all blocks
                for buffer in sat.sendBufferSatsIntra:
                    index = 0
                    while index < len(buffer[1]):
                        block = buffer[1][index]
                        destination = block.destination.name
                        newPath = getShortestPath(sat.ID, destination, self.pathParam, graph)
                        if newPath == -1:
                            if len(buffer[0]) == 1:
                                buffer[0].pop(index)
                                buffer[1].pop(index)
                                buffer[0].append(sat.env.event())
                            else:
                                buffer[0].pop(index)
                                buffer[1].pop(index)
                            continue
                        path = None
                        # splice old and new path
                        for i, step in enumerate(block.path):
                            if step[0] == sat.ID:
                                path = block.path[:i] + newPath
                                break
                        if path is None:
                            print("no path to sat:")
                            print(block)
                            exit()
                        block.isNewPath = True
                        block.oldPath = block.path
                        block.newPath = newPath
                        block.path = path
                        index += 1

                for buffer in sat.sendBufferSatsInter:
                    index = 0
                    while index < len(buffer[1]):
                        block = buffer[1][index]
                        destination = block.destination.name
                        newPath = getShortestPath(sat.ID, destination, self.pathParam, graph)
                        if newPath == -1:
                            if len(buffer[0]) == 1:
                                buffer[0].pop(index)
                                buffer[1].pop(index)
                                buffer[0].append(sat.env.event())
                            else:
                                buffer[0].pop(index)
                                buffer[1].pop(index)
                            continue
                        path = None
                        # splice old and new path
                        for i, step in enumerate(block.path):
                            if step[0] == sat.ID:
                                path = block.path[:i] + newPath
                                break
                        if path is None:
                            print("no path to sat:")
                            print(block)
                            exit()
                        block.isNewPath = True
                        block.oldPath = block.path
                        block.newPath = newPath
                        block.path = path
                        index += 1

                index = 0
                while index < len(sat.sendBufferGT[1]):
                    block = sat.sendBufferGT[1][index]
                    destination = block.destination.name
                    newPath = getShortestPath(sat.ID, destination, self.pathParam, graph)
                    if newPath == -1:
                        if len(sat.sendBufferGT[0]) == 1:
                            sat.sendBufferGT[0].pop(index)
                            sat.sendBufferGT[1].pop(index)
                            sat.sendBufferGT[0].append(sat.env.event())
                        else:
                            sat.sendBufferGT[0].pop(index)
                            sat.sendBufferGT[1].pop(index)
                        continue
                    path = None
                    # splice old and new path
                    for i, step in enumerate(block.path):
                        if step[0] == sat.ID:
                            path = block.path[:i] + newPath
                            break
                    if path is None:
                        print("no path to GT:")
                        print(block)
                        exit()
                    block.isNewPath = True
                    block.oldPath = block.path
                    block.newPath = newPath
                    block.path = path
                    index += 1

                index = 0
                while index < len(sat.tempBlocks):
                    block = sat.tempBlocks[index]
                    destination = block.destination.name
                    newPath = getShortestPath(sat.ID, destination, self.pathParam, graph)

                    if newPath == -1:
                        block.path = -1
                        if len(sat.tempBlocks[0]) == 1:
                            sat.tempBlocks[0].pop(index)
                            sat.tempBlocks[1].pop(index)
                            sat.tempBlocks[0].append(sat.env.event())
                        else:
                            sat.tempBlocks[0].pop(index)
                            sat.tempBlocks[1].pop(index)
                        continue

                    path = None
                    # splice old and new path
                    for i, step in enumerate(block.path):
                        if step[0] == sat.ID:
                            path = block.path[:i] + newPath
                            break
                    if path is None:
                        print("no path from Temp:")
                        print(block)
                        exit()
                    block.isNewPath = True
                    block.oldPath = block.path
                    block.newPath = newPath
                    block.path = path
                    index += 1

                # find neighboring satellites
                neighbors = list(nx.neighbors(graph, sat.ID))
                itt = 0
                neighborSatsInter = []
                for sat2 in sats:
                    if sat2.ID in neighbors:
                        # we only care about the satellite if it is an inter-plane ISL
                        # we assume intra-plane ISLs will not change
                        if sat2.in_plane != sat.in_plane:
                            dataRate = nx.path_weight(graph, [sat2.ID, sat.ID], "dataRateOG")
                            distance = nx.path_weight(graph, [sat2.ID, sat.ID], "slant_range")
                            neighborSatsInter.append((distance, sat2, dataRate))
                        itt += 1
                        if itt == len(neighbors):
                            break
                sat.interSats = neighborSatsInter
                # list of blocks to be redistributed
                blocksToDistribute = []

                ### inter-plane ISLs ###

                sat.newBuffer = [True for _ in range(len(neighborSatsInter))]

                # make a list of False entries for each current neighbor
                sameSats = [False for _ in range(len(neighborSatsInter))]

                buffers = [None for _ in range(len(neighborSatsInter))]
                processes = [None for _ in range(len(neighborSatsInter))]

                # go through each process/buffer
                #   - check if the satellite is still there:
                #       - if it is, change the corresponding False to True, handle blocks and add process and buffer references to temporary list
                #       - if it is not, remove blocks from buffer and stop process
                for bufferIndex, buffer in enumerate(sat.sendBufferSatsInter):
                    # check if the satellite is still there
                    isPresent = False
                    for neighborIndex, neighbor in enumerate(neighborSatsInter):
                        if buffer[2] == neighbor[1].ID:
                            isPresent = True
                            sameSats[neighborIndex] = True

                            ## handle blocks
                            # check if there are blocks in the buffer
                            if buffer[1]:
                                # find index of satellite in block's path
                                index = None
                                for i, step in enumerate(buffer[1][0].path):
                                    if sat.ID == step[0]:
                                        index = i
                                        break

                                # check if next step in path corresponds to buffer's satellite
                                if buffer[1][0].path[index + 1][0] == buffer[2]:
                                    # add all but the first block to redistribution list
                                    for block in buffer[1][1:]:
                                        blocksToDistribute.append((block.checkPoints[-1], block))

                                    # add buffer with only first block present to temp list
                                    buffers[neighborIndex] = ([sat.env.event().succeed()], [sat.sendBufferSatsInter[bufferIndex][1][0]], buffer[2])
                                    processes[neighborIndex] = sat.sendBlocksSatsInter[bufferIndex]
                                else:
                                    # add all blocks to redistribution list
                                    for block in buffer[1]:
                                        blocksToDistribute.append((block.checkPoints[-1], block))
                                    # reset buffer
                                    buffers[neighborIndex] = ([sat.env.event()], [], buffer[2])

                                    # reset process
                                    sat.sendBlocksSatsInter[bufferIndex].interrupt()
                                    processes[neighborIndex] = sat.env.process(sat.sendBlock(neighbor, True, False))

                            else: # there are no blocks in the buffer
                                # add buffer and remake process
                                buffers[neighborIndex] = sat.sendBufferSatsInter[bufferIndex]
                                sat.sendBlocksSatsInter[bufferIndex].interrupt()
                                processes[neighborIndex] = sat.env.process(sat.sendBlock(neighbor, True, False))
                                # sendBlocksSatsInter[bufferIndex]

                            break
                    if not isPresent:
                        # add blocks to redistribution list
                        for block in buffer[1]:
                            blocksToDistribute.append((block.checkPoints[-1], block))
                        # stop process
                        sat.sendBlocksSatsInter[bufferIndex].interrupt()

                # make buffer and process for new neighbors(s)
                # - go through list of previously false entries:
                #   - check  entry for each neighbor:
                #       - if False, create buffer and process for new neighbor
                # - clear temporary list of processes and buffers
                for entryIndex, entry in enumerate(sameSats):
                    if not entry:
                        buffers[entryIndex] = ([sat.env.event()], [], neighborSatsInter[entryIndex][1].ID)
                        processes[entryIndex] = sat.env.process(sat.sendBlock(neighborSatsInter[entryIndex], True, False))

                # overwrite buffers and processes
                sat.sendBlocksSatsInter = processes
                sat.sendBufferSatsInter = buffers

                ### intra-plane ISLs ###
                # check blocks for each buffer
                for bufferIndex, buffer in enumerate(sat.sendBufferSatsIntra):
                    ## handle blocks
                    # check if there are blocks in the buffer
                    if buffer[1]:
                        # find index of satellite in block's path
                        index = None
                        for i, step in enumerate(buffer[1][0].path):
                            if sat.ID == step[0]:
                                index = i
                                break

                        # check if next step in path corresponds to buffer's satellite
                        if buffer[1][0].path[index + 1][0] == buffer[2]:
                            # add all but the first block to redistribution list
                            for block in buffer[1][1:]:
                                blocksToDistribute.append((block.checkPoints[-1], block))

                            # remove all but the first block and event from the buffer
                            length = len(sat.sendBufferSatsIntra[bufferIndex][1]) - 1
                            for _ in range(length):
                                sat.sendBufferSatsIntra[bufferIndex][1].pop(1)
                                sat.sendBufferSatsIntra[bufferIndex][0].pop(1)

                        else:
                            # add all blocks to redistribution list
                            for block in buffer[1]:
                                blocksToDistribute.append((block.checkPoints[-1], block))
                            # reset buffer
                            sat.sendBufferSatsIntra[bufferIndex] = ([sat.env.event()], [], buffer[2])

                            # reset process
                            sat.sendBlocksSatsIntra[bufferIndex].interrupt()
                            sat.sendBlocksSatsIntra[bufferIndex] = sat.env.process(sat.sendBlock(sat.intraSats[bufferIndex], True, True))

                ### GSL ###
                # check if satellite has a linked GT
                if sat.linkedGT is not None:
                    sat.adjustDownRate()

                    # check if it had a sendBlocksGT process
                    if sat.sendBlocksGT:
                        # check if there are any blocks in the buffer
                        if sat.sendBufferGT[1]:
                            # check if linked GT is the same as the destination of first block in sendBufferGT
                            if sat.sendBufferGT[1][0].destination != sat.linkedGT:
                                sat.sendBlocksGT[0].interrupt()
                                sat.sendBlocksGT = []

                                # remove blocks from queue and add to list of blocks which should be redistributed
                                for block in sat.sendBufferGT[1]:
                                    blocksToDistribute.append(
                                        (block.checkPoints[-1], block))  # (latest checkpoint time, block)
                                sat.sendBufferGT = ([sat.env.event()], [])

                                # make new send process for new linked GT
                                sat.sendBlocksGT.append(
                                    sat.env.process(sat.sendBlock((sat.GTDist, sat.linkedGT), False)))
                            else:
                                # keep the first block in the buffer and let process continue
                                for block in sat.sendBufferGT[1][1:]:
                                    blocksToDistribute.append(
                                        (block.checkPoints[-1], block))  # (latest checkpoint time, block)
                                length = len(sat.sendBufferGT[1]) - 1
                                for _ in range(length):
                                    sat.sendBufferGT[1].pop(1) # pop all but the first block
                                    sat.sendBufferGT[0].pop(1) # pop all but the first event

                        else:  # there are no blocks in the buffer
                            sat.sendBlocksGT[0].interrupt()
                            sat.sendBlocksGT = []
                            sat.sendBufferGT = ([sat.env.event()], [])
                            # make new send process for new linked GT
                            sat.sendBlocksGT.append(sat.env.process(sat.sendBlock((sat.GTDist, sat.linkedGT), False)))

                    else:  # it had no process running
                        # there should be no blocks in the GT buffer, but just in case - if there are none, then the for loop will not run
                        # remove blocks from queue and add to list of blocks which should be redistributed
                        for block in sat.sendBufferGT[1]:
                            blocksToDistribute.append((block.checkPoints[-1], block))  # (latest checkpoint time, block)
                        sat.sendBufferGT = ([sat.env.event()], [])

                        # make new send process for new linked GT
                        sat.sendBlocksGT.append(sat.env.process(sat.sendBlock((sat.GTDist, sat.linkedGT), False)))

                else:  # no linked GT
                    # check if there is a sendBlocksGT process
                    if sat.sendBlocksGT:
                        sat.sendBlocksGT[0].interrupt()
                        sat.sendBlocksGT = []

                        # remove blocks from queue and add to list of blocks which should be redistributed
                        for block in sat.sendBufferGT[1]:
                            blocksToDistribute.append((block.checkPoints[-1], block))  # (latest checkpoint time, block)
                        sat.sendBufferGT = ([sat.env.event()], [])

                # sort blocks by arrival time at satellite
                blocksToDistribute.sort()
                # add blocks to the correct queues based on next step in their path
                # since the blocks list is sorted by arrival time, the order in the new queues is correct
                for block in blocksToDistribute:
                    # get this satellite's index in the blocks path
                    index = None
                    for i, step in enumerate(block[1].path):
                        if sat.ID == step[0]:
                            index = i

                    # check if next step in path is GT (last step in path)
                    if index == len(block[1].path) - 2:
                        # add block to GT send-buffer
                        if not sat.sendBufferGT[0][0].triggered:
                            sat.sendBufferGT[0][0].succeed()
                            sat.sendBufferGT[1].append(block[1])
                        else:
                            newEvent = sat.env.event().succeed()
                            sat.sendBufferGT[0].append(newEvent)
                            sat.sendBufferGT[1].append(block[1])
                    else:
                        # get ID of next sat and find if it is intra or inter
                        ID = None
                        isIntra = False
                        for neighborSat in sat.intraSats:
                            id = neighborSat[1].ID
                            if id == block[1].path[index + 1][0]:
                                ID = neighborSat[1].ID
                                isIntra = True
                        for neighborSat in sat.interSats:
                            id = neighborSat[1].ID
                            if id == block[1].path[index + 1][0]:
                                ID = neighborSat[1].ID

                        if ID is not None:
                            sendBuffer = None
                            # find send-buffer for the satellite
                            if isIntra:
                                for buffer in sat.sendBufferSatsIntra:
                                    if ID == buffer[2]:
                                        sendBuffer = buffer
                            else:
                                for buffer in sat.sendBufferSatsInter:
                                    if ID == buffer[2]:
                                        sendBuffer = buffer

                            # add block to buffer
                            if not sendBuffer[0][0].triggered:
                                sendBuffer[0][0].succeed()
                                sendBuffer[1].append(block[1])
                            else:
                                newEvent = sat.env.event().succeed()
                                sendBuffer[0].append(newEvent)
                                sendBuffer[1].append(block[1])
                        else:
                            print("buffer for next satellite in path could not be found")

    def updateSatelliteProcessesRL(self, graph):
        """
        This function does not work correctly! The remaking of processes and queues fails when the satellites move
        enough so that new links must be formed.

        This function takes into account that the paths are not complete and the next step may not have been chosen yet.

        Function which ensures all processes on all satellites are updated after constellation movement. This is done in
        several steps:
            - All blocks waiting to be sent or currently being sent has their paths updated.
            - ISLs are updated with references to new inter-orbit satellites (intra-orbit links do not change).
                - This includes updating buffer if ISL is changed
                - It also includes remaking send-process if ISL is changed
                - Despite intra-orbit links not changing, blocks in an intra-orbit buffer may have to be moved.
            - GSL is updated:
                - Depending on new status - whether the satellite has a GSL or not - and past status - whether the
                satellite had a GSL or not - GSL buffer and process is handled accordingly.
            - All blocks not currently being transmitted to a satellite/GT, which is still present as a ISL or GSL, are
            redistributed to send-buffers according to their arrival time at the satellite.

        This function differentiates from the simple version by allowing continued operation of send-processes after
        constellation movement if the link is not broken.
        """
        sats = []
        for plane in self.LEO:
            for sat1 in plane.sats:
                sats.append(sat1)

        for plane in self.LEO:
            for sat in plane.sats:
                # get next step for all blocks
                # doing this here assumes that the constellation movement will have a limited effect on the links
                # and that the queue sizes will not change significantly.

                # intra satellite buffers
                for buffer in sat.sendBufferSatsIntra:
                    index = 0
                    while index < len(buffer[1]):
                        block = buffer[1][index]

                        if len(block.QPath) > 4:  # the block does not come from a gateway
                            if sat.QLearning:
                                nextHop = sat.QLearning.makeAction(block, sat,
                                                                    sat.orbPlane.earth.gateways[0].graph,
                                                                    sat.orbPlane.earth, prevSat=(
                                        findByID(sat.orbPlane.earth, block.QPath[len(block.QPath) - 3][0])))
                            else:
                                nextHop = sat.orbPlane.earth.DDQNA.makeDeepAction(block, sat,
                                                                                   sat.orbPlane.earth.gateways[
                                                                                       0].graph,
                                                                                   sat.orbPlane.earth, prevSat=(
                                        findByID(sat.orbPlane.earth, block.QPath[len(block.QPath) - 3][0])))
                        else:
                            if sat.QLearning:
                                nextHop = sat.QLearning.makeAction(block, sat,
                                                                    sat.orbPlane.earth.gateways[0].graph,
                                                                    sat.orbPlane.earth)
                            else:
                                nextHop = sat.orbPlane.earth.DDQNA.makeDeepAction(block, sat,
                                                                                   sat.orbPlane.earth.gateways[
                                                                                       0].graph,
                                                                                   sat.orbPlane.earth)

                        if nextHop != 0:
                            block.QPath[-2] = nextHop
                            pathPlot = block.QPath.copy()
                            pathPlot.pop()
                        else:
                            pathPlot = block.QPath.copy()

                        # If printPath plots an image for every action taken. Prints 1/10 of blocks. # ANCHOR plot action earth 1
                        #################################################################
                        if sat.orbPlane.earth.printPaths:
                            if int(block.ID[len(block.ID) - 1]) == 0:
                                os.makedirs(sat.orbPlane.earth.outputPath + '/pictures/',
                                            exist_ok=True)  # create output path
                                outputPath = sat.orbPlane.earth.outputPath + '/pictures/' + block.ID + '_' + str(
                                    len(block.QPath)) + '_'
                                plotShortestPath(sat.orbPlane.earth, pathPlot, outputPath)
                        #################################################################

                        # path = block.QPath  # if there is Q-Learning the path will be repalced with the QPath
                        index += 1

                # inter satellite buffers
                for buffer in sat.sendBufferSatsInter:
                    index = 0
                    while index < len(buffer[1]):
                        block = buffer[1][index]

                        if len(block.QPath) > 4:  # the block does not come from a gateway
                            if sat.QLearning:
                                nextHop = sat.QLearning.makeAction(block, sat,
                                                                   sat.orbPlane.earth.gateways[0].graph,
                                                                   sat.orbPlane.earth, prevSat=(
                                        findByID(sat.orbPlane.earth, block.QPath[len(block.QPath) - 3][0])))
                            else:
                                nextHop = sat.orbPlane.earth.DDQNA.makeDeepAction(block, sat,
                                                                                  sat.orbPlane.earth.gateways[
                                                                                      0].graph,
                                                                                  sat.orbPlane.earth, prevSat=(
                                        findByID(sat.orbPlane.earth, block.QPath[len(block.QPath) - 3][0])))
                        else:
                            if sat.QLearning:
                                nextHop = sat.QLearning.makeAction(block, sat,
                                                                   sat.orbPlane.earth.gateways[0].graph,
                                                                   sat.orbPlane.earth)
                            else:
                                nextHop = sat.orbPlane.earth.DDQNA.makeDeepAction(block, sat,
                                                                                  sat.orbPlane.earth.gateways[
                                                                                      0].graph,
                                                                                  sat.orbPlane.earth)

                        if nextHop != 0:
                            block.QPath[-2] = nextHop
                            pathPlot = block.QPath.copy()
                            pathPlot.pop()
                        else:
                            pathPlot = block.QPath.copy()

                        # If printPath plots an image for every action taken. Prints 1/10 of blocks. # ANCHOR plot action earth 2
                        #################################################################
                        if sat.orbPlane.earth.printPaths:
                            if int(block.ID[len(block.ID) - 1]) == 0:
                                os.makedirs(sat.orbPlane.earth.outputPath + '/pictures/',
                                            exist_ok=True)  # create output path
                                outputPath = sat.orbPlane.earth.outputPath + '/pictures/' + block.ID + '_' + str(
                                    len(block.QPath)) + '_'
                                plotShortestPath(sat.orbPlane.earth, pathPlot, outputPath)
                        #################################################################

                        # path = block.QPath  # if there is Q-Learning the path will be repalced with the QPath
                        index += 1

                # down link buffers
                index = 0
                while index < len(sat.sendBufferGT[1]):
                    block = sat.sendBufferGT[1][index]

                    if len(block.QPath) > 4:  # the block does not come from a gateway
                        if sat.QLearning:
                            nextHop = sat.QLearning.makeAction(block, sat,
                                                               sat.orbPlane.earth.gateways[0].graph,
                                                               sat.orbPlane.earth, prevSat=(
                                    findByID(sat.orbPlane.earth, block.QPath[len(block.QPath) - 3][0])))
                        else:
                            nextHop = sat.orbPlane.earth.DDQNA.makeDeepAction(block, sat,
                                                                              sat.orbPlane.earth.gateways[
                                                                                  0].graph,
                                                                              sat.orbPlane.earth, prevSat=(
                                    findByID(sat.orbPlane.earth, block.QPath[len(block.QPath) - 3][0])))
                    else:
                        if sat.QLearning:
                            nextHop = sat.QLearning.makeAction(block, sat,
                                                               sat.orbPlane.earth.gateways[0].graph,
                                                               sat.orbPlane.earth)
                        else:
                            nextHop = sat.orbPlane.earth.DDQNA.makeDeepAction(block, sat,
                                                                              sat.orbPlane.earth.gateways[
                                                                                  0].graph,
                                                                              sat.orbPlane.earth)

                    if nextHop != 0:
                        block.QPath[-2] = nextHop
                        pathPlot = block.QPath.copy()
                        pathPlot.pop()
                    else:
                        pathPlot = block.QPath.copy()

                    # If printPath plots an image for every action taken. Prints 1/10 of blocks. # ANCHOR plot action earth 3
                    #################################################################
                    if sat.orbPlane.earth.printPaths:
                        if int(block.ID[len(block.ID) - 1]) == 0:
                            os.makedirs(sat.orbPlane.earth.outputPath + '/pictures/',
                                        exist_ok=True)  # create output path
                            outputPath = sat.orbPlane.earth.outputPath + '/pictures/' + block.ID + '_' + str(
                                len(block.QPath)) + '_'
                            plotShortestPath(sat.orbPlane.earth, pathPlot, outputPath)
                    #################################################################

                    # path = block.QPath  # if there is Q-Learning the path will be repalced with the QPath
                    index += 1

                # find neighboring satellites
                neighbors = list(nx.neighbors(graph, sat.ID))
                itt = 0
                neighborSatsInter = []
                for sat2 in sats:
                    if sat2.ID in neighbors:
                        # we only care about the satellite if it is an inter-plane ISL
                        # we assume intra-plane ISLs will not change
                        if sat2.in_plane != sat.in_plane:
                            dataRate = nx.path_weight(graph, [sat2.ID, sat.ID], "dataRateOG")
                            distance = nx.path_weight(graph, [sat2.ID, sat.ID], "slant_range")
                            neighborSatsInter.append((distance, sat2, dataRate))
                        itt += 1
                        if itt == len(neighbors):
                            break
                sat.interSats = neighborSatsInter
                # list of blocks to be redistributed
                blocksToDistribute = []

                ### inter-plane ISLs ###

                sat.newBuffer = [True for _ in range(len(neighborSatsInter))]

                # make a list of False entries for each current neighbor
                sameSats = [False for _ in range(len(neighborSatsInter))]

                buffers = [None for _ in range(len(neighborSatsInter))]
                processes = [None for _ in range(len(neighborSatsInter))]

                # go through each process/buffer
                #   - check if the satellite is still there:
                #       - if it is, change the corresponding False to True, handle blocks and add process and buffer references to temporary list
                #       - if it is not, remove blocks from buffer and stop process
                for bufferIndex, buffer in enumerate(sat.sendBufferSatsInter):
                    # check if the satellite is still there
                    isPresent = False
                    for neighborIndex, neighbor in enumerate(neighborSatsInter):
                        if buffer[2] == neighbor[1].ID:
                            isPresent = True
                            sameSats[neighborIndex] = True

                            ## handle blocks
                            # check if there are blocks in the buffer
                            if buffer[1]:
                                # find index of satellite in block's path
                                index = None
                                for i, step in enumerate(buffer[1][0].QPath):
                                    if sat.ID == step[0]:
                                        index = i
                                        break

                                # check if next step in path corresponds to buffer's satellite
                                if buffer[1][0].QPath[index + 1][0] == buffer[2]:
                                    # add all but the first block to redistribution list
                                    for block in buffer[1][1:]:
                                        blocksToDistribute.append((block.checkPoints[-1], block))

                                    # add buffer with only first block present to temp list
                                    buffers[neighborIndex] = ([sat.env.event().succeed()], [sat.sendBufferSatsInter[bufferIndex][1][0]], buffer[2])
                                    processes[neighborIndex] = sat.sendBlocksSatsInter[bufferIndex]
                                else:
                                    # add all blocks to redistribution list
                                    for block in buffer[1]:
                                        blocksToDistribute.append((block.checkPoints[-1], block))
                                    # reset buffer
                                    buffers[neighborIndex] = ([sat.env.event()], [], buffer[2])

                                    # reset process
                                    sat.sendBlocksSatsInter[bufferIndex].interrupt()
                                    processes[neighborIndex] = sat.env.process(sat.sendBlock(neighbor, True, False))

                            else: # there are no blocks in the buffer
                                # add buffer and remake process
                                buffers[neighborIndex] = sat.sendBufferSatsInter[bufferIndex]
                                sat.sendBlocksSatsInter[bufferIndex].interrupt()
                                processes[neighborIndex] = sat.env.process(sat.sendBlock(neighbor, True, False))
                                # sendBlocksSatsInter[bufferIndex]

                            break
                    if not isPresent:
                        # add blocks to redistribution list
                        for block in buffer[1]:
                            blocksToDistribute.append((block.checkPoints[-1], block))
                        # stop process
                        sat.sendBlocksSatsInter[bufferIndex].interrupt()

                # make buffer and process for new neighbors(s)
                # - go through list of previously false entries:
                #   - check  entry for each neighbor:
                #       - if False, create buffer and process for new neighbor
                # - clear temporary list of processes and buffers
                for entryIndex, entry in enumerate(sameSats):
                    if not entry:
                        buffers[entryIndex] = ([sat.env.event()], [], neighborSatsInter[entryIndex][1].ID)
                        processes[entryIndex] = sat.env.process(sat.sendBlock(neighborSatsInter[entryIndex], True, False))

                # overwrite buffers and processes
                sat.sendBlocksSatsInter = processes
                sat.sendBufferSatsInter = buffers

                ### intra-plane ISLs ###
                # check blocks for each buffer
                for bufferIndex, buffer in enumerate(sat.sendBufferSatsIntra):
                    ## handle blocks
                    # check if there are blocks in the buffer
                    if buffer[1]:
                        # find index of satellite in block's path
                        index = None
                        for i, step in enumerate(buffer[1][0].QPath):
                            if sat.ID == step[0]:
                                index = i
                                break

                        # check if next step in path corresponds to buffer's satellite
                        if buffer[1][0].QPath[index + 1][0] == buffer[2]:
                            # add all but the first block to redistribution list
                            for block in buffer[1][1:]:
                                blocksToDistribute.append((block.checkPoints[-1], block))

                            # remove all but the first block and event from the buffer
                            length = len(sat.sendBufferSatsIntra[bufferIndex][1]) - 1
                            for _ in range(length):
                                sat.sendBufferSatsIntra[bufferIndex][1].pop(1)
                                sat.sendBufferSatsIntra[bufferIndex][0].pop(1)

                        else:
                            # add all blocks to redistribution list
                            for block in buffer[1]:
                                blocksToDistribute.append((block.checkPoints[-1], block))
                            # reset buffer
                            sat.sendBufferSatsIntra[bufferIndex] = ([sat.env.event()], [], buffer[2])

                            # reset process
                            sat.sendBlocksSatsIntra[bufferIndex].interrupt()
                            sat.sendBlocksSatsIntra[bufferIndex] = sat.env.process(sat.sendBlock(sat.intraSats[bufferIndex], True, True))

                ### GSL ###
                # check if satellite has a linked GT
                if sat.linkedGT is not None:
                    sat.adjustDownRate()

                    # check if it had a sendBlocksGT process
                    if sat.sendBlocksGT:
                        # check if there are any blocks in the buffer
                        if sat.sendBufferGT[1]:
                            # check if linked GT is the same as the destination of first block in sendBufferGT
                            if sat.sendBufferGT[1][0].destination != sat.linkedGT:
                                sat.sendBlocksGT[0].interrupt()
                                sat.sendBlocksGT = []

                                # remove blocks from queue and add to list of blocks which should be redistributed
                                for block in sat.sendBufferGT[1]:
                                    blocksToDistribute.append(
                                        (block.checkPoints[-1], block))  # (latest checkpoint time, block)
                                sat.sendBufferGT = ([sat.env.event()], [])

                                # make new send process for new linked GT
                                sat.sendBlocksGT.append(
                                    sat.env.process(sat.sendBlock((sat.GTDist, sat.linkedGT), False)))
                            else:
                                # keep the first block in the buffer and let process continue
                                for block in sat.sendBufferGT[1][1:]:
                                    blocksToDistribute.append(
                                        (block.checkPoints[-1], block))  # (latest checkpoint time, block)
                                length = len(sat.sendBufferGT[1]) - 1
                                for _ in range(length):
                                    sat.sendBufferGT[1].pop(1) # pop all but the first block
                                    sat.sendBufferGT[0].pop(1) # pop all but the first event

                        else:  # there are no blocks in the buffer
                            sat.sendBlocksGT[0].interrupt()
                            sat.sendBlocksGT = []
                            sat.sendBufferGT = ([sat.env.event()], [])
                            # make new send process for new linked GT
                            sat.sendBlocksGT.append(sat.env.process(sat.sendBlock((sat.GTDist, sat.linkedGT), False)))

                    else:  # it had no process running
                        # there should be no blocks in the GT buffer, but just in case - if there are none, then the for loop will not run
                        # remove blocks from queue and add to list of blocks which should be redistributed
                        for block in sat.sendBufferGT[1]:
                            blocksToDistribute.append((block.checkPoints[-1], block))  # (latest checkpoint time, block)
                        sat.sendBufferGT = ([sat.env.event()], [])

                        # make new send process for new linked GT
                        sat.sendBlocksGT.append(sat.env.process(sat.sendBlock((sat.GTDist, sat.linkedGT), False)))

                else:  # no linked GT
                    # check if there is a sendBlocksGT process
                    if sat.sendBlocksGT:
                        sat.sendBlocksGT[0].interrupt()
                        sat.sendBlocksGT = []

                        # remove blocks from queue and add to list of blocks which should be redistributed
                        for block in sat.sendBufferGT[1]:
                            blocksToDistribute.append((block.checkPoints[-1], block))  # (latest checkpoint time, block)
                        sat.sendBufferGT = ([sat.env.event()], [])

                # sort blocks by arrival time at satellite
                try:
                    blocksToDistribute.sort()
                except Exception as e:
                    print(f"Caught an exception: {e}")
                    print(f'Something wrong with: \n{blocksToDistribute}')
                # add blocks to the correct queues based on next step in their path
                # since the blocks list is sorted by arrival time, the order in the new queues is correct
                for block in blocksToDistribute:
                    # get this satellite's index in the blocks path
                    index = None
                    for i, step in enumerate(block[1].QPath):
                        if sat.ID == step[0]:
                            index = i

                    # check if next step in path is GT (last step in path)
                    if index == len(block[1].QPath) - 2:
                        # add block to GT send-buffer
                        if not sat.sendBufferGT[0][0].triggered:
                            sat.sendBufferGT[0][0].succeed()
                            sat.sendBufferGT[1].append(block[1])
                        else:
                            newEvent = sat.env.event().succeed()
                            sat.sendBufferGT[0].append(newEvent)
                            sat.sendBufferGT[1].append(block[1])
                    else:
                        # get ID of next sat and find if it is intra or inter
                        ID = None
                        isIntra = False
                        for neighborSat in sat.intraSats:
                            id = neighborSat[1].ID
                            if id == block[1].QPath[index + 1][0]:
                                ID = neighborSat[1].ID
                                isIntra = True
                        for neighborSat in sat.interSats:
                            id = neighborSat[1].ID
                            if id == block[1].QPath[index + 1][0]:
                                ID = neighborSat[1].ID

                        if ID is not None:
                            sendBuffer = None
                            # find send-buffer for the satellite
                            if isIntra:
                                for buffer in sat.sendBufferSatsIntra:
                                    if ID == buffer[2]:
                                        sendBuffer = buffer
                            else:
                                for buffer in sat.sendBufferSatsInter:
                                    if ID == buffer[2]:
                                        sendBuffer = buffer

                            # add block to buffer
                            if not sendBuffer[0][0].triggered:
                                sendBuffer[0][0].succeed()
                                sendBuffer[1].append(block[1])
                            else:
                                newEvent = sat.env.event().succeed()
                                sendBuffer[0].append(newEvent)
                                sendBuffer[1].append(block[1])
                        else:
                            print("buffer for next satellite in path could not be found")

    def updateGTPaths(self):
        """
        Updates all paths for all GTs going to all other GTs and ensures that all blocks waiting to be sent has the
        correct path.
        """
        # make new paths for all GTs
        for GT in self.gateways:
            for destination in self.gateways:
                if GT != destination:
                    if destination.linkedSat[0] is not None and GT.linkedSat[0] is not None:
                        path = getShortestPath(GT.name, destination.name, self.pathParam, GT.graph)
                        GT.paths.update({destination.name: path})


                    else:
                        GT.paths.update({destination.name: []})
                        print("no path from gateway!!")

            # update paths for all blocks in send-buffer
            for block in GT.sendBuffer[1]:
                block.path = GT.paths[block.destination.name]
                block.isNewPath = True
                block.QPath = [block.path[0], block.path[1], block.path[len(block.path) - 1]]
                # We add a Qpath field for the Q-Learning case. Only source and destination will be added
                # after that, every hop will be added at the second last position.

    def getGSLDataRates(self):
        upDataRates = []
        downDataRates = []
        for GT in self.gateways:
            if GT.linkedSat[0] is not None:
                upDataRates.append(GT.dataRate)

        for orbit in self.LEO:
            for satellite in orbit.sats:
                if satellite.linkedGT is not None:
                    downDataRates.append(satellite.downRate)

        return upDataRates, downDataRates

    def getISLDataRates(self):
        interDataRates = []
        highRates = 0
        for orbit in self.LEO:
            for satellite in orbit.sats:
                for satData in satellite.interSats:
                    if satData[2] > 3e9:
                        highRates += 1
                    interDataRates.append(satData[2])
        return interDataRates

    def moveConstellation(self, env, deltaT=3600, getRates = False):
        """
        Simpy process function:

        Moves the constellations in terms of the Earth's rotation and moves the satellites within the constellations.
        The movement is based on the time that has passed since last constellation movement and is defined by the
        "deltaT" variable.

        After the satellites have been moved a process of re-linking all links, both GSLs and ISLs, is conducted where
        the paths for all blocks are re-made, the blocks are moved (if necessary) to the correct buffers, and all
        processes managing the send-buffers are checked to ensure they will still work correctly.
        """

        # Get the data rate for a intra plane ISL - used for testing
        if getRates:
            intraRate.append(self.LEO[0].sats[0].intraSats[0][2])

        while True:
            if getRates:
                # get data rates for all inter plane ISLs and all GSLs (up and down) - used for testing
                upDataRates, downDataRates = self.getGSLDataRates()
                inter = self.getISLDataRates()

                for val in upDataRates:
                    upGSLRates.append(val)

                for val in downDataRates:
                    downGSLRates.append(val)

                for val in inter:
                    interRates.append(val)

            yield env.timeout(deltaT)

            # clear satellite references on all GTs
            for GT in self.gateways:
                GT.satsOrdered = []
                GT.linkedSat = (None, None)

            # rotate constellation and satellites
            for constellation in self.LEO:
                constellation.rotate(ndeltas*deltaT)

            # relink satellites and GTs
            self.linkSats2GTs("Optimize")

            # create new graph and add references to all GTs for every rotation
            graph = createGraph(self)
            self.graph = graph
            for GT in self.gateways:
                GT.graph = graph

            if self.pathParam == 'Deep Q-Learning' or self.pathParam == 'Q-Learning':
                self.updateSatelliteProcessesRL(graph)
            else:
                self.updateSatelliteProcessesCorrect(graph)

            self.updateGTPaths()

    def testFlowConstraint1(self, graph):
        highestDist = (0,0)
        for GT in self.gateways:
            if 1/GT.linkedSat[0] > highestDist[0]:
                highestDist = (1/GT.linkedSat[0], GT)

        lowestDist = (1/highestDist[0], highestDist[1])

        toolargeDists = []

        for (u,v,c) in graph.edges.data("slant_range"):
            if c > lowestDist[0]:
                toolargeDists.append((u,v,c))

        print("number of edges with too large distance: {}".format(len(toolargeDists)))

    def testFlowConstraint2(self, graph):
        edgeWeights = nx.get_edge_attributes(graph, "slant_range")
        totalFailed = 0

        for GT in self.gateways[1:]:
            failed = False
            path = getShortestPath(self.gateways[0].name, GT.name, self.pathParam, graph)
            try:
                firstStep = GT.linkedSat[0]
            except KeyError:
                firstStep = edgeWeights[(path[1][0], path[0][0])]
                print(f'Keyerror in: {GT.name}')


            for index in range(1, len(path) - 2):
                try:
                    if edgeWeights[(path[index][0], path[index+1][0])] > firstStep:
                        failed = True
                except KeyError:
                    print(f'Keyerror 2 in: {GT.name}')
                    if edgeWeights[(path[index+1][0], path[index][0])] > firstStep:
                        failed = True
            if failed:
                print("{} could not create a path which adheres to flow constraints".format(GT.name))
                totalFailed += 1

        print("number of GT paths that cannot meet flow restraints: {}".format(totalFailed))

    def plotMap(self, plotGT = True, plotSat = True, path = None, bottleneck = None, save = False, ID=None, time=None):
        plt.figure()
        legend_properties = {'size': 10, 'weight': 'bold'}
        markerscale = 1.5

        if plotGT:
            for GT in self.gateways:
                scat1 = plt.scatter(GT.gridLocationX, GT.gridLocationY, marker='x', c='r', s=28, linewidth=1.5, label = GT.name)
                # if GT.linkedSat[0] is not None:
                    # scat1 = plt.scatter(GT.gridLocationX, GT.gridLocationY, marker='x', c='r', s=8, linewidth=0.5)
                    # gridSatX = int((0.5 + math.degrees(GT.linkedSat[1].longitude) / 360) * GT.totalX)
                    # gridSatY = int((0.5 - math.degrees(GT.linkedSat[1].latitude) / 180) * GT.totalY)
                    #scat2 = plt.scatter(gridSatX, gridSatY, marker='o', s=8, linewidth=0.5, color='r')
                    # print(GT.linkedSat[1])
                    # print(GT)

        if plotSat:
            colors = matplotlib.cm.rainbow(np.linspace(0, 1, len(self.LEO)))

            for plane, c in zip(self.LEO, colors):
                # print('------------------------------------------------------------')
                # print('Plane: ' + str(plane.ID))
                for sat in plane.sats:
                    gridSatX = int((0.5 + math.degrees(sat.longitude) / 360) * 1440)
                    gridSatY = int((0.5 - math.degrees(sat.latitude) / 180) * 720) #GT.totalY)
                    # scat2 = plt.scatter(gridSatX, gridSatY, marker='o', s=18, linewidth=0.5, color=c, label = sat.ID)
                    scat2 = plt.scatter(gridSatX, gridSatY, marker='o', s=18, linewidth=0.5, edgecolors='black', color=c, label=sat.ID)

                    # print('Longitude: ' + str(math.degrees(sat.longitude)) +  ', Grid X: ' + str(gridSatX) + '\nLatitude: ' + str(math.degrees(sat.latitude)) + ', Grid Y: ' + str(gridSatY))
                        # Longitude +-180º, latitude +-90º

        # Print path if given
        if path:
            # print('Plotting path between ' + path[0][0] + ' and ' + path[len(path)-1][0])
            if bottleneck:
                xValues = [[], [], []]
                yValues = [[], [], []]
                # bottleneck[1][-1] = 1 # used to test all links to ensure code is correct in plotting path and weakest link
                minimum = np.amin(bottleneck[1])
                length = len(path)
                index = 0
                arr = 0
                minFound = False

                while index < length:
                    xValues[arr].append(int((0.5 + path[index][1] / 360) * 1440))  # longitude
                    yValues[arr].append(int((0.5 - path[index][2] / 180) * 720))  # latitude
                    if not minFound:
                        if bottleneck[1][index] == minimum:
                            arr+=1
                            xValues[arr].append(int((0.5 + path[index][1] / 360) * 1440))  # longitude
                            yValues[arr].append(int((0.5 - path[index][2] / 180) * 720))  # latitude
                            xValues[arr].append(int((0.5 + path[index+1][1] / 360) * 1440))  # longitude
                            yValues[arr].append(int((0.5 - path[index+1][2] / 180) * 720))  # latitude
                            arr+=1
                            minFound = True
                    index += 1

                scat3 = plt.plot(xValues[0], yValues[0], 'b')
                scat3 = plt.plot(xValues[1], yValues[1], 'r')
                scat3 = plt.plot(xValues[2], yValues[2], 'b')
            else:
                xValues = []
                yValues = []
                for hop in path:
                    xValues.append(int((0.5 + hop[1] / 360) * 1440))     # longitude
                    yValues.append(int((0.5 - hop[2] / 180) * 720))      # latitude
                scat3 = plt.plot(xValues, yValues)  # , marker='.', c='b', linewidth=0.5, label = hop[0])

            # plt.legend([scat1, scat2, scat3], ['Ground Terminals', 'Satellites', 'Path'], loc=3, prop={'size': 7})

        if plotSat and plotGT:
            plt.legend([scat1, scat2], ['Gateways', 'Satellites'], loc=3, prop=legend_properties, markerscale=markerscale)
        elif plotSat:
            plt.legend([scat2], ['Satellites'], loc=3, prop=legend_properties, markerscale=markerscale)
        elif plotGT:
            plt.legend([scat1], ['Gateways'], loc=3, prop=legend_properties, markerscale=markerscale)

        plt.xticks([])
        plt.yticks([])

        cell_users = np.array(self.getCellUsers()).transpose()
        plt.imshow(cell_users, norm=LogNorm(), cmap='viridis')

        # plt.imshow(np.log10(np.array(self.getCellUsers()).transpose() + 1), )
        
        # Add title
        if time is not None and ID is not None:
            plt.title(f"Creation time: {time*1000:.2f}ms, block ID: {ID}")

        if save:
            plt.savefig("mapa.png", dpi=1000)
        # plt.title('LEO constellation and Ground Terminals')
        # plt.rcParams['figure.figsize'] = 36, 12  # adjust if figure is too big or small for screen
        # plt.colorbar(fraction=0.1)  # adjust fraction to change size of color bar
        # plt.show()

    def initializeQTables(self, NGT, hyperparams, g):
        '''
        QTables initialization at each satellite
        '''
        print('----------------------------')

        path = './Results/latency Test/Q-Learning/qTablesImport/qTablesExport/' + str(NGT) + 'GTs/'

        if importQVals:
            print('Importing Q-Tables from: ' + path)
        else:
            print('Initializing Q-tables...')
        
        i = 0
        for plane in self.LEO:
            for sat in plane.sats:
                i += 1
                if importQVals:
                    with open(path + sat.ID + '.npy', 'rb') as f:
                        qTable = np.load(f)
                    sat.QLearning = QLearning(NGT, hyperparams, self, g, sat, qTable=qTable)
                else:
                    sat.QLearning = QLearning(NGT, hyperparams, self, g, sat)

        if importQVals:
            print(str(i) + ' Q-Tables imported!')
        else:
            print(str(i) + ' Q-Tables created!')
        print('----------------------------')

    def plot3D(self):
        fig = plt.figure()
        ax = fig.add_subplot(projection='3d')

        xs = []
        ys = []
        zs = []
        xG = []
        yG = []
        zG = []
        for con in self.LEO:
            for sat in con.sats:
                xs.append(sat.x)
                ys.append(sat.y)
                zs.append(sat.z)
        ax.scatter(xs, ys, zs, marker='o')
        for GT in self.gateways:
            xG.append(GT.x)
            yG.append(GT.y)
            zG.append(GT.z)
        ax.scatter(xG, yG, zG, marker='^')
        plt.show()

    def __repr__(self):
        return 'total divisions in x = {}\n total divisions in y = {}\n total cells = {}\n window of operation ' \
               '(longitudes) = {}\n window of operation (latitudes) = {}'.format(
                self.total_x,
                self.total_y,
                self.total_cells,
                self.windowx,
                self.windowy)


class hyperparam:
    def __init__(self, pathing):
        '''
        Hyperparameters of the Q-Learning model
        '''
        self.alpha      = alpha
        self.gamma      = gamma
        self.epsilon    = epsilon
        self.ArriveR    = ArriveReward
        self.w1         = w1
        self.w2         = w2
        self.pathing    = pathing
        self.tau        = tau
        self.updateF    = updateF
        self.batchSize  = batchSize
        self.bufferSize = bufferSize
        self.hardUpdate = hardUpdate==1
        self.importQ    = importQVals
        self.MAX_EPSILON= MAX_EPSILON
        self.MIN_EPSILON= MIN_EPSILON
        self.LAMBDA     = LAMBDA
        self.printPath  = printPath
 
    def __repr__(self):
        return 'Hyperparameters:\nalpha: {}\ngamma: {}\nepsilon: {}\nw1: {}\nw2: {}\n'.format(
        self.alpha,
        self.gamma,
        self.epsilon,
        self.w1,
        self.w2)


# @profile
class QLearning:
    def __init__(self, NGT, hyperparams, earth, g, sat, qTable = None):
        '''
        Create a 6D numpy array to hold the current Q-values for each state and action pair: Q(s, a)
        The array contains 5 dimensions with the shape of the environment, as well as a 6th "action" dimension.
        The "action" dimension consists of 4 layers that will allow us to keep track of the Q-values for each possible action in each state
        The value of each (state, action) pair is initialized ranomly.
        '''
        satUp, satDown, satRight, satLeft = 3, 3, 3, 3
        linkedSats   = getlinkedSats(sat, g, earth)
        self.linkedSats =  {'U': linkedSats['U'],
                            'D': linkedSats['D'],
                            'R': linkedSats['R'],
                            'L': linkedSats['L']}

        self.actions         = ('U', 'D', 'R', 'L')     # Up, Down, Left, Right
        self.Destinations    = NGT

        self.nStates    = satUp*satDown*satRight*satLeft*NGT
        self.nActions   = len(self.actions)
                
        if qTable is None:  # initialize it randomly if we are not going to import it
            self.qTable = np.random.rand(satUp, satDown, satRight, satLeft, NGT, self.nActions)  # first 5 fields are states while 6th field is the action. 4050 values with 10 GTs

        else:
            self.qTable = qTable

        self.alpha  = hyperparams.alpha
        self.gamma  = hyperparams.gamma
        # self.epsilon= hyperparams.epsilon
        self.epsilon= []
        self.maxEps = hyperparams.MAX_EPSILON
        self.minEps = hyperparams.MIN_EPSILON
        self.w1     = hyperparams.w1
        self.w2     = hyperparams.w2

        self.oldState  = (0,0,0,0,0)
        self.oldAction = 0

    def makeAction(self, block, sat, g, earth, prevSat=None):
        '''
        This function will:
        1. Check if the destination is the linked gateway. In that case it will just return 0 and the block will be sent there.
        2. Observation of the environment in order to determine state space and get the linked satellites.
        3. Chooses an action. Random one (Exploration) or the most valuable one (Exploitation). If the direction of that action has no linked satellite, the QValue will be -inf
        4. Receive reward/penalty
            Penalties: If the block visits again the same satellite. Reward = -1
                       Another one directly proportional to the length of the destination queue.
            Reward: So far, it will be higher if it gets physically closer to the satellite
        5. Updates Q-Table of the previous hop (Agent) with the following information:
            1. Reward      : Time waited at satB Queue && slant range reduction.
            2. maxNewQValue: Max Q Value of all possible actions at the new agent.
            3. Old state-action taken at satA in order to know where to update the Q-Table. 
            Everytime satB receives a dataBlock from satA satB will send the information required to update satA QTable.
        '''

        # There is no 'Done' state, it will simply continue until the time stops
        # simplemente se va a recibir una recompensa positiva si el satelite al que envias el paquete es el linkado al destino de este

        # 1. check if the destination is the linked gateway. The value of this action becomes 10. # ANCHOR plots route of delivered package Q-Learning
        if sat.linkedGT and block.destination.name == sat.linkedGT.name:
            prevSat.QLearning.qTable[block.oldState][block.oldAction] = ArriveReward
            if drawDeliver:
                if int(block.ID[len(block.ID)-1]) == 0: # Draws 1/10 arrivals
                    os.makedirs(earth.outputPath + '/pictures/', exist_ok=True) # drawing delivered
                    outputPath = earth.outputPath + '/pictures/' + block.ID + '_' + str(len(block.QPath)) + '_'
                    plotShortestPath(earth, block.QPath, outputPath, ID=block.ID)
            
            return 0

        # 2. Observation of the environment
        newState = tuple(getState(block, sat, g, earth))
       
        # 3. Choose an action (the direction of the next hop)
        # randomly
        # if random.uniform(0, 1)<self.epsilon:
        if random.uniform(0, 1)<self.alignEpsilon(earth, sat) and explore:
            action = self.actions[random.randrange(len(self.actions))]
            while(self.linkedSats[action] == None): 
                action = self.actions[random.randrange(len(self.actions))]  # if that direction has no linked satellite
        
        # highest value
        else:
            qValues = self.qTable[newState]
            action  = self.actions[np.argmax(qValues)]                      # Most valuable action (The one that will give more reward) 
            while self.linkedSats[action] == None:
                self.qTable[newState][self.actions.index(action)] = -np.inf # change qTable if that action is not available
                action = self.actions[np.argmax(qValues)]

        destination = self.linkedSats[action]    # Action is the keyword of the chosen linked satellite, linkedSats is a dictionary with each satellite associated to its corresponding keyword

        # ACT -> [it is done outside, the next hop is added at sat.receiveBlock method to block.QPath]
        nextHop = [destination.ID, math.degrees(destination.longitude), math.degrees(destination.latitude)]

        # 4. Receive reward/penalty for the previous action
        if prevSat is not None:
            hop = [sat.ID, math.degrees(sat.longitude), math.degrees(sat.latitude)]
            # if the next hop was already visited before the reward will be -1
            if hop in block.QPath[:len(block.QPath)-2]:
                reward = againPenalty
            else:
                distanceReward = getDistanceReward(prevSat, sat, block.destination, self.w2)
                queueReward    = getQueueReward   (block.queueTime[len(block.queueTime)-1], self.w1)
                reward = distanceReward + queueReward

        # 5. Updates Q-Table 
        # Update QTable of previous Node (Agent, satellite) if it was not a gateway     
            nextMax     = np.max(self.qTable[newState]) # max value of next state given oldAction
            oldQValue   = prevSat.QLearning.qTable[block.oldState][block.oldAction]
            newQvalue   = (1-self.alpha) * oldQValue + self.alpha * (reward+self.gamma*nextMax) 
            prevSat.QLearning.qTable[block.oldState][block.oldAction] = newQvalue
            
        else:
            # prev node was a gateway, no need to compute the reward
            reward = 0

        # this will be saved always, except when the next hop is the destination, where the process will have already returned
        block.oldState  = newState
        block.oldAction = self.actions.index(action)

        earth.step += 1

        return nextHop

    def alignEpsilon(self, earth, sat):
        global      CurrentGTnumber
        epsilon     = self.minEps + (self.maxEps - self.minEps) * math.exp(-LAMBDA * earth.step/(decayRate*(CurrentGTnumber**2)))
        earth        .epsilon.append([epsilon, sat.env.now])
        return epsilon

    def __repr__(self):
            return '\n Nº of destinations = {}\n Action Space = {}\n Nº of states = {}\n qTable: {}'.format(
            self.Destinations,
            self.actions,
            self.nStates,
            self.qTable)


# @profile
class DDQNAgent:
    def __init__(self, NGT, hyperparams):   
        self.actions        = ('U', 'D', 'R', 'L')
        self.states         = ('UpLinked Up', 'UpLinked Down','UpLinked Right','UpLinked Left',                        # Up Link
                            'Up Latitude', 'Up Longitude',                                                             # Up positions
                            'DownLinked Up', 'DownLinked Down','DownLinked Right','DownLinked Left',                   # Down Link
                            'Down Latitude', 'Down Longitude',                                                         # Down positions
                            'RightLinked Up', 'RightLinked Down','RightLinked Right','RightLinked Left',               # Right Link
                            'Right Latitude', 'Right Longitude',                                                       # Right positions
                            'LeftLinked Up', 'LeftLinked Down','LeftLinked Right','LeftLinked Left',                   # Left Link
                            'Left Latitude', 'Left Longitude',                                                         # Left positions

                            'Actual latitude', 'Actual longitude',                                                     # Actual Position
                            'Destination latitude', 'Destination longitude')                                           # Destination Position

        print(f'State Space:\n {self.states}')
        print(f'Action Space:\n {self.actions}')
        self.actionSize     = len(self.actions)
        self.stateSize      = len(self.states)
        self.destinations   = NGT

        self.alpha  = hyperparams.alpha
        self.gamma  = hyperparams.gamma
        self.epsilon= []
        self.maxEps = hyperparams.MAX_EPSILON
        self.minEps = hyperparams.MIN_EPSILON
        self.w1     = hyperparams.w1
        self.w2     = hyperparams.w2
        self.tau    = hyperparams.tau
        self.updateF= hyperparams.updateF
        self.batchS = hyperparams.batchSize
        self.bufferS= hyperparams.bufferSize
        self.hardUpd= hyperparams.hardUpdate
        self.importQ= hyperparams.importQ

        self.step   = 0
        self.i      = 0

        self.replayBuffer  = []
        self.experienceReplay = ExperienceReplay(self.bufferS)
        # self.optimizer        = Adam(learning_rate=self.alpha, clipnorm=Clipnorm)
        self.loss_function    = losses.Huber()

        if not self.importQ:
            '''
            The compile method is used to configure the learning process of qNetwork and it sets the optimizer and loss function that the model will use to learn during training.
            It only is done in the q network because in the DDQN algorithm, we train the qNetwork with the data from the environment and update qTarget periodically.

            In DDQN the qNetwork is updated with the learning process defined by the loss and optimizer, but the qTarget network used for evaluation and stability purpose is
            a frozen version of qNetwork, which is updated periodically and not during the learning process.
            '''
            # The first model makes the predictions for Q-values which are used to make a action
            self.qNetwork = self.createModel()
            print('----------------------------------')
            print(f"Neural Network Created!!!")
            print('----------------------------------')
            self.qNetwork.summary()
            # tf.keras.utils.plot_model(self.qNetwork, to_file='qNetwork.png', show_shapes=True)
            # self.qNetwork.compile(loss='mse', optimizer=Adam(learning_rate=self.alpha))

            # Build a target model for the prediction of future rewards.
            # The weights of a target model get updated every updateF steps thus when the loss between the Q-values is calculated the target Q-value is stable
            # self.qTarget  = self.createModel()
        else:
            # if import models, it will import a trained model
            try:
                global nnpath
                self.qNetwork = keras.models.load_model(nnpath)
                print('----------------------------------')
                print(f"Neural Network imported from:\n {nnpath}!!!")
                print('----------------------------------')
                self.qNetwork.summary()
            except FileNotFoundError:
                print('----------------------------------')
                print(f"Neural Network path wrong")
                print('----------------------------------')
        
    def getNextHop(self, newState, linkedSats, sat):
        '''
        Given a new observed state and the linkied satellites, it will return the next hop
        '''
        # randomly (Exploration)
        if random.uniform(0, 1)<self.alignEpsilon(self.step, sat) and explore:
            actIndex = random.randrange(self.actionSize)
            action   = self.actions[actIndex]
            while(linkedSats[action] == None):   # if that direction has no linked satellite
                self.experienceReplay.store(newState, actIndex, unavPenalty, newState, False) # stores experience, repeats randomly
                action = self.actions[random.randrange(len(self.actions))]

        # highest value (Exploitation)
        else:
            # Predict 
            qValues = self.qNetwork.predict(newState, verbose = 0)               # NOTE NN.predict. Gets next hop. state structure in debugging
            actIndex = np.argmax(qValues)
            action   = self.actions[actIndex]
            while(linkedSats[action] == None):              # the chosen action has no linked satellite. NEGATIVE REWARD and store it, motherfucker.
                self.experienceReplay.store(newState, actIndex, unavPenalty, newState, False) # from state to the same state, reward -1, not terminated
                qValues[0][actIndex] = -np.inf              # it will not be chosen again (as the model has still not trained with that)
                actIndex = np.argmax(qValues)               # find again for the highest value
                action   = self.actions[actIndex]  

        destination = linkedSats[action]    # Action is the keyword of the chosen linked satellite, linkedSats is a dictionary with 
                                            # each satellite associated to its corresponding keyword
        
        # ACT -> [it is done outside, the next hop is added at sat.receiveBlock method to block.QPath]
        return [destination.ID, math.degrees(destination.longitude), math.degrees(destination.latitude)], actIndex

    def makeDeepAction(self, block, sat, g, earth, prevSat=None):
        '''
        There is no 'Done' state, it will simply continue until the time stops.
        This function will:
        1. Observation of the environment in order to determine state space and get the linked satellites to the one making the action.
        2. Check if the destination is the linked gateway. 
            If the satellite sent the block to the satellite linked to the destination GW, it will receive a reward of 10.
            The previous satellite will match the destination of the block to the linked gateway of the next state (I hope and I guess)
            In that case it will just return 0 and the block will be sent there.
        3. Chooses an action.
            Random one (Exploration)
            The most valuable one (Exploitation).
            If the direction of that action has no linked satellite, that action will not be available.
       4. Receive reward/penalty
            Penalties: If the block visits again the same satellite. Reward = -1
                       If it tries to send the block to a direction where there is no linked satellite.
                       Another one directly proportional to the length of the destination queue.
            Reward: One proportional to the slant range reduction, meaning that it will be higher if it gets physically closer to the satellite.
                    Another one when it reaches the destination
        5. Store experience from the previous hop (Agent) with the following information:
            1. Reward      : Time waited at satB Queue && slant range reduction.
            2. maxNewQValue: Max Q Value of all possible actions at the new agent.
            3. Old state-action taken at satA in order to know where to update the NNs. 
            Everytime satB receives a dataBlock from satA satB will send the information required to update the NNs.        
            Unlike in regular Q-Learning, in this step we just have to store the experience into the experience replay buffer.
            It will be updated automatically taking a random batch from the buffer every n iterations.
            We will store the old state of the block, the action index taken there, the reward received and the new state it moved into.
        6. Update the qTarget every n iterations.
        '''
        # 1. Observe the state and search for the satellites linked to the one making the action
        linkedSats  = getlinkedSats(sat, g, earth)
        newState    = getDeepState(block, sat, linkedSats)

        if newState is None: 
            earth.lostBlocks+=1
            return 0
        self.step   += 1

        # 2. Check if the destination is the linked gateway. The reward is 10 here and goes to the previous satellite. # ANCHOR plot delivered deep NN
        if sat.linkedGT and (block.destination.ID == sat.linkedGT.ID):    # Compare IDs
            if distanceRew == 4:
                distanceReward  = getDistanceRewardV4(prevSat, sat, block.destination, self.w2)
                queueReward     = getQueueReward   (block.queueTime[len(block.queueTime)-1], self.w1)
                reward          = distanceReward + queueReward + ArriveReward
                self.experienceReplay.store(block.oldState, block.oldAction, reward, newState, True)
                # self.experienceReplay.store(block.oldState, block.oldAction, ArriveReward, newState, True)
            else:
                self.experienceReplay.store(block.oldState, block.oldAction, ArriveReward, newState, True)

            if TrainThis: self.train(sat) # FIXME why here a train?? should not be here. Make a test without this when the model is stable
            if drawDeliver:
                if int(block.ID[len(block.ID)-1]) == 0: # Draws 1/10 arrivals
                    os.makedirs(earth.outputPath + '/pictures/', exist_ok=True) # drawing delivered
                    outputPath = earth.outputPath + '/pictures/' + block.ID + '_' + str(len(block.QPath)) + '_'
                    plotShortestPath(earth, block.QPath, outputPath, ID=block.ID, time = block.creationTime)
            return 0

        # 3. Choose an action (the direction of the next hop)
        nextHop, actIndex = self.getNextHop(newState, linkedSats, sat)
        
        # 4. Computes reward/penalty for the previous action
        if prevSat is not None:
            hop = [sat.ID, math.degrees(sat.longitude), math.degrees(sat.latitude)]
            # if the next hop was already visited before the reward will be -1
            if hop in block.QPath[:len(block.QPath)-2]:
                again = againPenalty
            else:
                again = 0

            if distanceRew == 1:
                distanceReward  = getDistanceReward(prevSat, sat, block.destination, self.w2)
            elif distanceRew == 2:
                prevLinkedSats  = getlinkedSats(prevSat, g, earth)
                distanceReward  = getDistanceRewardV2(prevSat, sat, prevLinkedSats['U'], prevLinkedSats['D'], prevLinkedSats['R'], prevLinkedSats['L'], block.destination, self.w2)
            elif distanceRew == 3:
                prevLinkedSats  = getlinkedSats(prevSat, g, earth)
                distanceReward  = getDistanceRewardV3(prevSat, sat, prevLinkedSats['U'], prevLinkedSats['D'], prevLinkedSats['R'], prevLinkedSats['L'], block.destination, self.w2)
            elif distanceRew == 4:
                distanceReward  = getDistanceRewardV4(prevSat, sat, block.destination, self.w2)
            
            queueReward     = getQueueReward   (block.queueTime[len(block.queueTime)-1], self.w1)
            reward          = distanceReward + again + queueReward

        # 5. Store the experience of previous Node (Agent, satellite) if it was not a gateway  
            self.experienceReplay.store(block.oldState, block.oldAction, reward, newState, False) # action index

        # 6. Learning, train the Q-Network at every time we store experience
            if TrainThis and self.step % nTrain == 0:
                self.train(sat)

        else:
            # prev node was a gateway, no need to compute the reward
            reward = 0

        # this will be saved always, except when the next hop is the destination, where the process will have already returned
        block.oldState  = newState
        block.oldAction = actIndex
        
        return nextHop

    def alignEpsilon(self, step, sat): # the epsilon is reduced with time
        '''
        Updates epsilon value at each step
        0.01+0.99*e^(-0.0005*10000):
        0     -> 1
        1000  -> 0.61
        5000  -> 0.091
        10000 -> 0.01667
        '''
        global      CurrentGTnumber
        epsilon     = self.minEps + (self.maxEps - self.minEps) * math.exp(-LAMBDA * step/(decayRate*(CurrentGTnumber**2)))
        self        .epsilon.append([epsilon, sat.env.now])
        return epsilon

    def alignQTarget(self, hardUpdate = False): # Soft one is done every step
        '''
        This function is not used now since the q target only exists in double deep q learning and it is not implemented.
        Updates the qTarget NN with the weights of the qNetwork.

        The choice between using hard updates or soft updates for the target network depends on the specific requirements of your problem and the properties of your data.

        Hard updates, where the target network is updated with the latest weights of the Q-network, could be more beneficial when the data changes frequently and quickly.
        However, if the data is relatively stable and consistent, then hard updates may cause the target network to oscillate too much, destabilizing the training of the Q-network.

        Soft updates, where the target network's parameters are updated with a moving average of the Q-network's parameters, are more stable than hard updates and can help the
        Q-network converge more smoothly. This is because soft updates gradually propagate the changes in the Q-network's parameters to the target network, rather than suddenly 
        switching to the latest weights. This can be a better choice when the data is relatively stable and consistent, or when you're worried about potential stability issues in
        the training process.

        Ultimately, the best way to determine which method is more convenient is through experimentation with your specific problem and dataset.
        '''
        if hardUpdate:
            self.i += 1
            if self.i == self.updateF:
                self.qTarget.set_weights(self.qNetwork.get_weights()) # NOTE qTarget gets qNetrowk values
                print(f"Q-Target network hard updated!!!")
                self.i = 0

        else:
            for t, e in zip(self.qTarget.trainable_variables, 
            self.qNetwork.trainable_variables): t.assign(t * (1 - self.tau) + e * self.tau)

    def createModel(self):
        model = Sequential()
        model.add(Dense(32, activation='relu', input_shape=(self.stateSize,), kernel_initializer='random_uniform'))
        model.add(Dense(32, activation='relu', kernel_initializer='random_uniform'))
        model.add(Dense(self.actionSize, activation='linear'))
        model.compile(loss='mse', optimizer='adam')
        # optimizer = Adam(learning_rate=learningRate)  # You can adjust the learning rate as needed
        # model.compile(loss='mse', optimizer=optimizer)
        return model

    def train(self, sat):
        if self.experienceReplay.buffeSize < self.batchS*3:
            return -1

        # 1. Get a random batch from the experience
        miniBatch = self.experienceReplay.getBatch(self.batchS)
        states, actions, rewards, nextStates, Dones = self.experienceReplay.getArraysFromBatch(miniBatch)
        states      = states.reshape((self.batchS,self.stateSize))
        nextStates  = nextStates.reshape((self.batchS,self.stateSize))
         
        # 2. Compute expected reward
        futureRewards = self.qNetwork.predict(nextStates, verbose = 0)          # NOTE NN.predict. Gets future rewards
        expectedRewards = rewards + self.gamma*np.max(futureRewards, axis=1)

        # 3. Mask for the actions
        acts = np.eye(self.actionSize)[actions]

        # 4. Stop Loss
        if stopLoss and len(sat.orbPlane.earth.loss)>nLosses:
            savedLoss = sat.orbPlane.earth.loss
            last_n_losses = [sample[0] for sample in savedLoss[-nLosses:]]
            average = sum(last_n_losses) / nLosses 
            sat.orbPlane.earth.lossAv.append(average)
            if average < lThreshold:
                global TrainThis
                TrainThis = False
                print('----------------------------------')
                print(f"STOP LOSS ACTIVATED")
                print(f'Last {nLosses} losses: {last_n_losses}')
                print(f'Simulation time: {sat.env.now}')
                print('----------------------------------')
                return 0

        # 5. fit the model and save the loss
        loss = self.qNetwork.fit(states, acts * expectedRewards[:, None], batch_size=self.batchS, epochs=1, verbose=0) # NOTE qNetwork fit
        sat.orbPlane.earth.loss.append([loss.history['loss'][0], sat.env.now])
        

# @profile
class ExperienceReplay:
    def __init__(self, maxlen = 100):
        '''
        This is a buffer that holds information that are used during training process.

        Deque (Doubly Ended Queue). Deque is preferred over a list in the cases where we need quicker append and pop operations
        from both the ends of the container, as deque provides an O(1) time complexity for append and pop operations as compared
        to a list that provides O(n) time complexity
        '''
        self.buffer = deque(maxlen=maxlen)

    def store(self, state, action, reward, nextState, terminated):
        '''
        appends a set of (state, action, reward, next state, terminated) to the experience replay buffer
        '''
        # if the buffer is full, it behave as a FIFO
        self.buffer.append((state, action, reward, nextState, terminated)) # stores the number of the action

    def getBatch(self, batchSize):
        '''
        gets a random batch of samples from all the samples
        '''
        return random.sample(self.buffer, batchSize)

    def getArraysFromBatch(self, batch):
        '''
        gets the batch data divided into fields
        '''
        states  = np.array([x[0] for x in batch])
        actions = np.array([x[1] for x in batch])
        rewards = np.array([x[2] for x in batch])
        next_st = np.array([x[3] for x in batch])
        dones   = np.array([x[4] for x in batch])
        
        return states, actions, rewards, next_st, dones

    @property
    def buffeSize(self):
        '''
        a pythonic way to use getters and setters in object-oriented programming
        this decorator is a built-in function that allows us to define methods that can be accessed like an attribute
        '''
        return len(self.buffer)
        

###############################################################################
############################   Functions    ###################################
###############################################################################


# @profile
def initialize(env, popMapLocation, GTLocation, distance, inputParams, movementTime, totalLocations, outputPath):
    """
    Initializes an instance of the earth with cells from a population map and gateways from a csv file.
    During initialisation, several steps are performed to prepare for simulation:
        - GTs find the cells that within their ground coverage areas and "link" to them.
        - A certain LEO Constellation with a given architecture is created.
        - Satellites are distributed out to GTs so each GT connects to one satellite (if possible) and each satellite
        only has one connected GT.
        - A graph is created from all the GSLs and ISLs
        - Paths are created from each GT to all other GTs
        - Buffers and processes are created on all GTs and satellites used for sending the blocks throughout the network
    """

    constellationType = inputParams['Constellation'][0]
    fraction = inputParams['Fraction'][0]
    testType = inputParams['Test type'][0]
    # pathing  = inputParams['Pathing'][0]

    if testType == "Rates":
        getRates = True
    else:
        getRates = False

    # Load earth and gateways
    earth = Earth(env, popMapLocation, GTLocation, constellationType, inputParams, movementTime, totalLocations, getRates, outputPath=outputPath)

    print(earth)
    print()

    earth.linkCells2GTs(distance)
    earth.linkSats2GTs("Optimize")
    graph = createGraph(earth)
    
    for gt in earth.gateways:
        gt.graph = graph


    paths = []
    # make paths for all source destination pairs
    for GT in earth.gateways:
        for destination in earth.gateways:
            if GT != destination:
                if destination.linkedSat[0] is not None and GT.linkedSat[0] is not None:
                    path = getShortestPath(GT.name, destination.name, earth.pathParam, GT.graph)
                    GT.paths[destination.name] = path
                    paths.append(path)

    # add ISl references to all satellites and adjust data rate to GTs
    sats = []
    for plane in earth.LEO:
        for sat in plane.sats:
            sats.append(sat)

    fiveNeighbors = ([0],[])

    pathNames = [name[0] for name in path]

    for plane in earth.LEO:
        for sat in plane.sats:

            if sat.linkedGT is not None:
                sat.adjustDownRate()
                # make a process for the GSL from sat to GT
                sat.sendBlocksGT.append(sat.env.process(sat.sendBlock((sat.GTDist, sat.linkedGT), False)))
            neighbors = list(nx.neighbors(graph, sat.ID))
            if len(neighbors) == 5:
                fiveNeighbors[0][0] += 1
                fiveNeighbors[1].append(neighbors)
            itt = 0
            for sat2 in sats:

                if sat2.ID in neighbors:
                    dataRate = nx.path_weight(graph,[sat2.ID, sat.ID], "dataRateOG")
                    distance = nx.path_weight(graph,[sat2.ID, sat.ID], "slant_range")

                    # check if satellite is inter- or intra-plane
                    if sat2.in_plane == sat.in_plane:
                        sat.intraSats.append((distance, sat2, dataRate))
                        # make a send buffer for intra ISL ([self.env.event()], [DataBlock(0, 0, "0", 0)], 0)
                        sat.sendBufferSatsIntra.append(([sat.env.event()], [], sat2.ID))
                        # make a process for intra ISL
                        sat.sendBlocksSatsIntra.append(sat.env.process(sat.sendBlock((distance, sat2, dataRate), True, True)))
                    else:
                        sat.interSats.append((distance, sat2, dataRate))
                        # make a send buffer for inter ISL ([self.env.event()], [DataBlock(0, 0, "0", 0)], 0)
                        sat.sendBufferSatsInter.append(([sat.env.event()], [], sat2.ID))
                        # make a process for inter ISL
                        sat.sendBlocksSatsInter.append(sat.env.process(sat.sendBlock((distance, sat2, dataRate), True, False)))

                    itt += 1
                    if itt == len(neighbors):
                        break

    bottleneck2, minimum2 = findBottleneck(paths[1], earth, False)
    bottleneck1, minimum1 = findBottleneck(paths[0], earth, False, minimum2)

    print('Traffic generated per GT (totalAvgFlow per Milliard):')
    print('----------------------------------')
    for GT in earth.gateways:
        mins = []
        if GT.linkedSat[0] is not None:

            for pathKey in GT.paths:
                _, minimum = findBottleneck(GT.paths[pathKey], earth)
                mins.append(minimum)
            if GT.dataRate < GT.linkedSat[1].downRate:
                GT.getTotalFlow(1, "Step", 1, GT.dataRate, fraction)  # using data rate of the GSL uplink
            else:
                GT.getTotalFlow(1, "Step", 1, GT.linkedSat[1].downRate, fraction)  # using data rate of the GSL downlink
    print('----------------------------------')

    # In case we want to train the constellation we initialize the Q-Tables
    if pathing == 'Q-Learning' or pathing == 'Deep Q-Learning':
        hyperparams = hyperparam(pathing)
    if pathing == 'Deep Q-Learning':
        earth.DDQNA = DDQNAgent(len(earth.gateways), hyperparams)

    # save hyperparams
    if pathing == 'Q-Learning' or pathing == "Deep Q-Learning":
        saveHyperparams(earth.outputPath, inputParams, hyperparams)

    if pathing == 'Q-Learning':
        '''
        Q-Agents are initialized here
        '''
        earth.initializeQTables(len(earth.gateways), hyperparams, graph)

    return earth, graph, bottleneck1, bottleneck2


# @profile
def findBottleneck(path, earth, plot = False, minimum = None):
    # Find the bottleneck of a route.
    bottleneck = [[], [], [], []]
    for GT in earth.gateways:
        if GT.name == path[0][0]:
            bottleneck[0].append(str(path[0][0].split(",")[0]) + "," + str(path[1][0]))
            bottleneck[1].append(GT.dataRate)
            bottleneck[2].append(GT.latitude)
            if minimum:
                bottleneck[3].append(minimum/GT.dataRate)

    for i, step in enumerate(path[1:], 1):
        for orbit in earth.LEO:
            for satellite in orbit.sats:
                if satellite.ID == step[0]:

                    for sat in satellite.interSats:
                        if sat[1].ID == path[i + 1][0]:
                            bottleneck[0].append(str(path[i][0]) + "," + str(path[i + 1][0]))
                            bottleneck[1].append(sat[2])
                            bottleneck[2].append(satellite.latitude)
                            if minimum:
                                bottleneck[3].append(minimum / sat[2])
                    for sat in satellite.intraSats:
                        if sat[1].ID == path[i + 1][0]:
                            bottleneck[0].append(str(path[i][0]) + "," + str(path[i + 1][0]))
                            bottleneck[1].append(sat[2])
                            bottleneck[2].append(satellite.latitude)
                            if minimum:
                                bottleneck[3].append(minimum / sat[2])
    for GT in earth.gateways:
        if GT.name == path[-1][0]:
            bottleneck[0].append(str(path[-2][0]) + "," + str(path[-1][0].split(",")[0]))
            bottleneck[1].append(GT.linkedSat[1].downRate)
            bottleneck[2].append(GT.latitude)
            if minimum:
                bottleneck[3].append(minimum/GT.dataRate)

    if plot:
        earth.plotMap(True,True,path, bottleneck)
        plt.show()
        plt.close()

    minimum = np.amin(bottleneck[1])
    return bottleneck, minimum


# @profile
def create_Constellation(specific_constellation, env, earth):

    if specific_constellation == "small":               # Small Walker star constellation for tests.
        print("Using small walker Star constellation")
        P = 4					# Number of orbital planes
        N_p = 8 				# Number of satellites per orbital plane
        N = N_p*P				# Total number of satellites
        height = 1000e3			# Altitude of deployment for each orbital plane (set to the same altitude here)
        inclination_angle = 53	# Inclination angle for the orbital planes, set to 90 for Polar
        Walker_star = True		# Set to True for Walker star and False for Walker Delta
        min_elevation_angle = 30

    elif specific_constellation =="Kepler":
        print("Using Kepler constellation design")
        P = 7#7
        N_p = 20#20
        N = N_p*P
        height = 600e3
        inclination_angle = 98.6
        Walker_star = True
        min_elevation_angle = 30

    elif specific_constellation =="Iridium_NEXT":
        print("Using Iridium NEXT constellation design")
        P = 6
        N_p = 11
        N = N_p*P
        height = 780e3
        inclination_angle = 86.4
        Walker_star = True
        min_elevation_angle = 30

    elif specific_constellation =="OneWeb":
        print("Using OneWeb constellation design")
        P = 18
        N = 648
        N_p = int(N/P)
        height = 1200e3
        inclination_angle = 86.4
        Walker_star = True
        min_elevation_angle = 30

    elif specific_constellation =="Starlink":			# Phase 1 550 km altitude orbit shell
        print("Using Starlink constellation design")
        P = 72
        N = 1584
        N_p = int(N/P)
        height = 550e3
        inclination_angle = 53
        Walker_star = False
        min_elevation_angle = 25

    elif specific_constellation == "Test":
        print("Using a test constellation design")
        P = 30                     # Number of orbital planes
        N = 1200                   # Total number of satellites
        N_p = int(N/P)             # Number of satellites per orbital plane
        height = 600e3             # Altitude of deployment for each orbital plane (set to the same altitude here)
        inclination_angle = 86.4   # Inclination angle for the orbital planes, set to 90 for Polar
        Walker_star = True         # Set to True for Walker star and False for Walker Delta
        min_elevation_angle = 30
    else:
        print("Not valid Constellation Name")
        P = np.NaN
        N_p = np.NaN
        N = np.NaN
        height = np.NaN
        inclination_angle = np.NaN
        Walker_star = False
        exit()

    distribution_angle = 2*math.pi  # Angle in which the orbital planes are distributed in

    if Walker_star:
        distribution_angle /= 2
    orbital_planes = []

    # Add orbital planes and satellites
    # Orbital_planes.append(orbital_plane(0, height, 0, math.radians(inclination_angle), N_p, min_elevation_angle, 0))
    for i in range(0, P):
        orbital_planes.append(OrbitalPlane(str(i), height, i*distribution_angle/P, math.radians(inclination_angle), N_p,
                                           min_elevation_angle, str(i) + '_', env, earth))

    return orbital_planes


###############################################################################
###############################  Create Graph   ###############################
###############################################################################


def get_direction(Satellites):
    '''
    Gets the direction of the satellites so each transceiver antenna can be set to one direction.
    '''
    N = len(Satellites)
    direction = np.zeros((N,N), dtype=np.int8)
    for i in range(N):
        epsilon = -Satellites[i].inclination    # orbital plane inclination
        for j in range(N):
            direction[i,j] = np.sign(Satellites[i].y*math.sin(epsilon)+
                                    Satellites[i].z*math.cos(epsilon)-Satellites[j].y*math.sin(epsilon)-
                                    Satellites[j].z*math.cos(epsilon))
    return direction


def get_pos_vectors_omni(Satellites):
    '''
    Given a list of satellites returns a list with x, y, z coordinates and the plane where they are (meta)
    '''
    N = len(Satellites)
    Positions = np.zeros((N,3))
    meta = np.zeros(N, dtype=np.int_)
    for n in range(N):
        Positions[n,:] = [Satellites[n].x, Satellites[n].y, Satellites[n].z]
        meta[n] = Satellites[n].in_plane

    return Positions, meta


def get_slant_range(edge):
        return(edge.slant_range)


@numba.jit  # Using this decorator you can mark a function for optimization by Numba's JIT compiler
def get_slant_range_optimized(Positions, N):
    '''
    returns a matrix with the all the distances between the satellites (optimized)
    '''
    slant_range = np.zeros((N,N))
    for i in range(N):
        slant_range[i,i] = math.inf
        for j in range(i+1,N):
            slant_range[i,j] = np.linalg.norm(Positions[i,:] - Positions[j,:])
    slant_range += np.transpose(slant_range)
    return slant_range


@numba.jit  # Using this decorator you can mark a function for optimization by Numba's JIT compiler
def los_slant_range(_slant_range, _meta, _max, _Positions):
    '''
    line of sight slant range
    '''
    _slant_range_new = np.copy(_slant_range)
    _N = len(_slant_range)
    for i in range(_N):
        for j in range(_N):
            if _slant_range_new[i,j] > _max[_meta[i], _meta[j]]:
                _slant_range_new[i,j] = math.inf
    return _slant_range_new


def get_data_rate(_slant_range_los, interISL):
    """
    Given a matrix of slant ranges returns a matrix with all the shannon dataRates possibles between all the satellites.
    """
    speff_thresholds = np.array(
        [0, 0.434841, 0.490243, 0.567805, 0.656448, 0.789412, 0.889135, 0.988858, 1.088581, 1.188304, 1.322253,
         1.487473, 1.587196, 1.647211, 1.713601, 1.779991, 1.972253, 2.10485, 2.193247, 2.370043, 2.458441,
         2.524739, 2.635236, 2.637201, 2.745734, 2.856231, 2.966728, 3.077225, 3.165623, 3.289502, 3.300184,
         3.510192, 3.620536, 3.703295, 3.841226, 3.951571, 4.206428, 4.338659, 4.603122, 4.735354, 4.933701,
         5.06569, 5.241514, 5.417338, 5.593162, 5.768987, 5.900855])
    lin_thresholds = np.array(
        [1e-10, 0.5188000389, 0.5821032178, 0.6266138647, 0.751622894, 0.9332543008, 1.051961874, 1.258925412,
         1.396368361, 1.671090614, 2.041737945, 2.529297996, 2.937649652, 2.971666032, 3.25836701, 3.548133892,
         3.953666201, 4.518559444, 4.83058802, 5.508076964, 6.45654229, 6.886522963, 6.966265141, 7.888601176,
         8.452788452, 9.354056741, 10.49542429, 11.61448614, 12.67651866, 12.88249552, 14.48771854, 14.96235656,
         16.48162392, 18.74994508, 20.18366364, 23.1206479, 25.00345362, 30.26913428, 35.2370871, 38.63669771,
         45.18559444, 49.88844875, 52.96634439, 64.5654229, 72.27698036, 76.55966069, 90.57326009])

    pathLoss = 10*np.log10((4 * math.pi * _slant_range_los * interISL.f / Vc)**2)   # Free-space pathloss in dB
    snr = 10**((interISL.maxPtx_db + interISL.G - pathLoss - interISL.No)/10)       # SNR in times
    shannonRate = interISL.B*np.log2(1+snr)                                         # data rates matrix in bits per second

    speffs = np.zeros((len(_slant_range_los),len(_slant_range_los)))

    for n in range(len(_slant_range_los)):
        for m in range(len(_slant_range_los)):
            feasible_speffs = speff_thresholds[np.nonzero(lin_thresholds <= snr[n,m])]
            if feasible_speffs.size == 0:
                speffs[n, m] = 0
            else:
                speffs[n,m] = interISL.B * feasible_speffs[-1]

    return speffs


def markovianMatchingTwo(earth):
    '''
    Returns a list of edge class elements. Each edge stands for a connection between two satellites. On that class
    the slant range and the data rate between both satellites are stored as attributes.
    This function is for satellites with two transceivers antennas that will enable two inter-plane ISL each one
    in a different direction.
    Intra-plane ISL are also computed and returned in _A_Markovian list

    It is not the optimal solution, but it is from 10 to 1000x faster.
    Minimizes the total cost of the constellation matching problem.
    '''

    _A_Markovian    = []    # list with all the
    Satellites      = []    # list with all the satellites
    W_M             = []    # list with the distances of every possible link between sats
    covered         = set() # Set with the connections already covered

    for plane in earth.LEO:
        for sat in plane.sats:
            Satellites.append(sat)

    N = len(Satellites)

    interISL = RFlink(
        frequency=26e9,
        bandwidth=500e6,
        maxPtx=10,
        aDiameterTx=0.26,
        aDiameterRx=0.26,
        pointingLoss=0.3,
        noiseFigure=2,
        noiseTemperature=290,
        min_rate=10e3
    )

    # max slant range for each orbit
    ###########################################################
    M = len(earth.LEO)              # Number of planes in LEO
    Max_slnt_rng = np.zeros((M,M))  # All ISL slant ranges must me lowe than 'Max_slnt_rng[i, j]'

    Orb_heights  = []
    for plane in earth.LEO:
        Orb_heights.append(plane.h)
        maxSlantRange = plane.sats[0].maxSlantRange

    for _i in range(M):
        for _j in range(M):
            Max_slnt_rng[_i,_j] = (np.sqrt( (Orb_heights[_i] + Re)**2 - Re**2 ) +
                                np.sqrt( (Orb_heights[_j] + Re)**2 - Re**2 ) )


    # Get data rate old method
    ###########################################################
    direction       = get_direction(Satellites)             # get both directions of the satellites to use the two transceivers
    Positions, meta = get_pos_vectors_omni(Satellites)      # position and plane of all the satellites
    slant_range     = get_slant_range_optimized(Positions, N)                       # matrix with all the distances between satellties
    slant_range_los = los_slant_range(slant_range, meta, Max_slnt_rng, Positions)   # distance matrix but if d>dMax, d=infinite
    shannonRate     = get_data_rate(slant_range_los, interISL)                      # max dataRate

    '''
    Compute all possible edges between different plane satellites whose transceiver antennas are free.
    if slant range > max slant range then that edge is not added
    '''
    ###########################################################
    for i in range(N):
        for j in range(i+1,N):
            if Satellites[i].in_plane != Satellites[j].in_plane and ((i,direction[i,j]) not in covered) and ((j,direction[j,i]) not in covered):
                if slant_range_los[i,j] < 6000e3: # math.inf:
                    W_M.append(edge(Satellites[i].ID,Satellites[j].ID,slant_range_los[i,j],direction[i,j], direction[j,i], shannonRate[i,j]))

    W_sorted=sorted(W_M,key=get_slant_range) # NOTE we could choose shannonRate instead

    # from all the possible links adds only the uncovered with the best weight possible
    ###########################################################
    while W_sorted:
        if  ((W_sorted[0].i,W_sorted[0].dji) not in covered) and ((W_sorted[0].j,W_sorted[0].dij) not in covered):
            _A_Markovian.append(W_sorted[0])
            covered.add((W_sorted[0].i,W_sorted[0].dji))
            covered.add((W_sorted[0].j,W_sorted[0].dij))
        W_sorted.pop(0)

    # add intra-ISL edges
    ###########################################################
    nPlanes = len(earth.LEO)
    for plane in earth.LEO:
        nPerPlane = len(plane.sats)
        for sat in plane.sats:
            sat.findNeighbours(earth)

            # upper neighbour
            i = sat.in_plane        *nPerPlane    +sat.i_in_plane

            j = sat.upper.in_plane  *nPerPlane    +sat.upper.i_in_plane

            _A_Markovian.append(edge(sat.ID, sat.upper.ID,  # satellites IDs
            slant_range_los[i, j],                          # distance between satellites
            direction[i,j], direction[j,i],                 # directions
            shannonRate[i,j]))                              # Max dataRate

            # lower neighbour
            j = sat.lower.in_plane  *nPerPlane    +sat.lower.i_in_plane

            _A_Markovian.append(edge(sat.ID, sat.lower.ID,  # satellites IDs
            slant_range_los[i, j],                          # distance between satellites
            direction[i,j], direction[j,i],                 # directions
            shannonRate[i,j]))                              # Max dataRate

    return _A_Markovian


def createGraph(earth):
    '''
    Each satellite has two transceiver antennas that are connected to the closest satellite in east and west direction to a satellite
    from another plane (inter-ISL). Each satellite also has anoteher two transceiver antennas connected to the previous and to the
    following satellite at their orbital plane (intra-ISL).
    A graph is created where each satellite is a node and each connection is an edge with a specific weight based either on the
    inverse of the maximum data rate achievable, total distance or number of hops.
    '''
    g = nx.Graph()

    # add LEO constellation
    ###############################
    for plane in earth.LEO:
        for sat in plane.sats:
            g.add_node(sat.ID, sat=sat)

    # add gateways and GSL edges
    ###############################
    for GT in earth.gateways:
        if GT.linkedSat[1]:
            g.add_node(GT.name, GT = GT)            # add GT as node
            g.add_edge(GT.name, GT.linkedSat[1].ID, # add GT linked sat as edge
            slant_range = GT.linkedSat[0],          # slant range
            invDataRate = 1/GT.dataRate,            # Inverse of dataRate
            dataRateOG = GT.dataRate,               # original shannon dataRate
            hop = 1)                                # in case we just want to count hops

    # add inter-ISL and intra-ISL edges
    ###############################
    markovEdges = markovianMatchingTwo(earth)
    for markovEdge in markovEdges:
        g.add_edge(markovEdge.i, markovEdge.j,  # source and destination IDs
        slant_range = markovEdge.slant_range,   # slant range
        dataRate = 1/markovEdge.shannonRate,    # Inverse of dataRate
        dataRateOG = markovEdge.shannonRate,    # Original shannon datRate
        hop = 1,                                # in case we just want to count hops
        dij = markovEdge.dij,
        dji = markovEdge.dji)

    return g


def getShortestPath(source, destination, weight, g):
    '''
    Gives you the shortest path between a source and a destination and plots it if desired.
    Uses the 'dijkstra' algorithm to compute the sortest path, where the total weight of the path can be either the sum of inverse
    of the maximumm dataRate achevable, the total slant range or the number of hops taken between source and destination.

    returns a list where each element is a sublist with the name of the node, its longitude and its latitude.
    '''

    path = []
    try:
        shortest = nx.shortest_path(g, source, destination, weight = weight)    # computes the shortest path [dataRate, slant_range, hops]
        for hop in shortest:                                                    # pre process the data so it can be used in the future
            key = list(g.nodes[hop])[0]
            if shortest.index(hop) == 0 or shortest.index(hop) == len(shortest)-1:
                path.append([hop, g.nodes[hop][key].longitude, g.nodes[hop][key].latitude])
            else:
                path.append([hop, math.degrees(g.nodes[hop][key].longitude), math.degrees(g.nodes[hop][key].latitude)])
    except Exception as e:
        print(f"getShortestPath Caught an exception: {e}")
        print('No path between ' + source + ' and ' + destination + ', check the graph to see more details.')
        return -1
    return path


def plotShortestPath(earth, path, outputPath, ID=None, time=None):
    earth.plotMap(True, True, path=path, ID=ID,time=time)
    plt.savefig(outputPath + 'popMap_' + path[0][0] + '_to_' + path[len(path)-1][0] + '.png', dpi = 500)
    # plt.show()
    plt.close()


def normalize(arr, t_min, t_max):
    norm_arr = []
    diff = t_max - t_min
    diff_arr = max(arr) - min(arr)
    for i in arr:
        temp = (((i - min(arr))*diff)/diff_arr) + t_min
        norm_arr.append(temp)
    return norm_arr


###############################################################################
#########################    Q-Tables - StateSpace    #########################
###############################################################################


def watchScores(earth, g):
    '''
    This function will print the scores of each satellite at that moment
    The satellites with any missing queue are those who does not have the 4 linked satellites. All of them are inter-plane ISL
    '''
    print('----------------------------------')
    print("SCORES:\n")
    print('----------------------------------')
    for plane in earth.LEO:
        for sat in plane.sats:
            print('-----------------')
            print(sat.ID + ": ")
            print('-----------------')
            for edge in list(g.edges(sat.ID)):
                if edge[1][0].isdigit():    # pos 1 regarding to the linked node and position 0 regarding to the first character of the linked node
                    print('Score between ' + str(edge) + ': ' + str(getSatScore(findByID(earth, edge[0]), findByID(earth, edge[1]), g)))
                else:
                    print('Gateway linked: ' + str(edge))


def findByID(earth, satID):
    '''
    given the ID of a satellite, this function will return the corresponding satellite object
    '''
    for plane in earth.LEO:
        for sat in plane.sats:
            if (sat.ID == satID):
                return sat


def computeOutliers(g):
    '''
    Given a graph, will return the throughput and slant range thresholds that will be used to find the outliers
    (Devices with bad conditions)
    '''
    # define outliers
    slantRanges = []
    dataRates   = []

    for edge in list(g.edges()):
        slantRanges.append(g.edges[edge]['slant_range'])
        dataRates  .append(g.edges[edge]['dataRateOG'])

    # Slant Range Outliers
    slantRanges = pd.Series(slantRanges)
    Q3 = slantRanges.describe()['75%']
    Q1 = slantRanges.describe()['25%']
    IQR = Q3 - Q1
    upperFence = Q3 + (1.5*IQR)

    # Data Rate Outliers
    dataRates = pd.Series(dataRates)
    Q3 = dataRates.describe()['75%']
    Q1 = dataRates.describe()['25%']
    IQR = Q3 - Q1
    lowerFence = Q1 - (1.5*IQR)

    return lowerFence, upperFence


def getQueues(sat, threshold=None, DDQN = False):
    '''
    When !DDQN, this function will return True if one of the satellite queues has a length over a limit or they are
    missing one link

    Each satellite has a queue for each link which includes both ISL and GSL (sat 2 GT). The Queues are implemented as
    tuples that contain a list of simpy events, a list of the data blocks, and the ID of the satellite for the link
    (there is no ID for the GT queues). The structure is tuple[list[Simpy.event], list[DataBlock], ID].
    The list of events will always have at least one event present which will be non-triggered when there are no blocks
    in the queue. When blocks are present, there will be as many triggered events as there are blocks.

    On the GTs, there is one queue which has the same structure as the queues for the GSLs on the satellites:
    tuple[list[Simpy.event], list[DataBlock]]

    ISLs Queues: sendBufferSats where each entry is a separate queue.
    GSLs Queues: sendBufferGT. While there will never be more than one queue in this list.
    GTs  Queues: sendBuffer which is just the tuple itself

    In our case we will just choose the highest queue of all the ISLs and compare it to a threshold

    The try excepts are for those cases where the linked satellite does not have the 4 linked satllites queues.
    IF THE SATELLITE DOES NOT HAVE 4 LINEKD SATELLITES IT WILL BE CONSIDERED AS HIGH QUEUE
    '''
    queuesLen = []
    infQueue  = False
    queuesDic = {'U': np.inf,
                 'D': np.inf,
                 'R': np.inf,
                 'L': np.inf}
    try:
       queuesLen.append(len(sat.sendBufferSatsIntra[0][1]))
       queuesDic['U'] = len(sat.sendBufferSatsIntra[0][1])
    except (IndexError, AttributeError):
        infQueue = True
    try:
       queuesLen.append(len(sat.sendBufferSatsIntra[1][1]))
       queuesDic['D'] = len(sat.sendBufferSatsIntra[1][1])

    except (IndexError, AttributeError):
        infQueue = True
    try:
        queuesLen.append(len(sat.sendBufferSatsInter[0][1]))
        queuesDic['R'] = len(sat.sendBufferSatsInter[0][1])
    except (IndexError, AttributeError):
        infQueue = True
    try:
        queuesLen.append(len(sat.sendBufferSatsInter[1][1]))
        queuesDic['L'] = len(sat.sendBufferSatsInter[1][1])
    except (IndexError, AttributeError):
        infQueue = True

    if not DDQN:
        return max(queuesLen) > threshold or infQueue
    else:
        return queuesDic


def hasBadConnection(satA, satB, thresholdSL, thresholdTHR, g):
    '''
    This function will return true if the satellites distance between them > trheshold or if their throughpuyt < trheshold
    They are far away or the link is weak
    '''
    slantRange     = g.edges[satA.ID, satB.ID]['slant_range']
    throughputSats = g.edges[satA.ID, satB.ID]['dataRateOG']

    return (slantRange > thresholdSL or throughputSats < thresholdTHR)


def getSatScore(satA, satB, g):
    '''
    This function will compute the score of sending the package from satA to satB
    0: (Low  slant range || high throughput) && low queue
    1:  High slant range && low  throughput  && low queue
    2:  High queue

    Queue threshold:
    As high queue threshold we have set 125 packets, which is the 92 percentile of all the queues when we have 13 GTs
    (The moment when we start having congestion with slant range policy). The waiting time of a queue with 125 blocks
    is 9 msg (Each packet in the queue lasts ~0.072ms)
    '''
    thresholdQueue = 125
    thresholdTHR, thresholdSL = computeOutliers(g)

    if satB is None or getQueues(satB, thresholdQueue):
        return 2
    elif hasBadConnection(satA, satB, thresholdSL, thresholdTHR, g):
        return 1
    else:
        return 0


# @profile
def getDeepSatScore(queueLength):
    # return 1 if queueLength > infQueue else (int(np.floor(queueVals*np.log10(queueLength + 1)/np.log10(infQueue))))/queueVals
    return queueVals if queueLength > infQueue else int(np.floor(queueVals*np.log10(queueLength + 1)/np.log10(infQueue)))


def getDirection(satA, satB):
    '''
    Returns the direction of going from satA to satB.
    If the node is not previous to the linked one we will treat it as a reversed way.
    If the node was

    Dir 1 (Go Upper): lower  -> higher latitude
    Dir 2 (Go Lower): higher -> lower  latitude
    Dir 3 (Go Right): lower  -> higher longitude
    Dir 4 (Go left) : higher -> lower  longitude
    higher orbital plane, (Not always, this direction is taken from the markovian matching)
    lower  orbital plane, (Not always, this direction is taken from the markovian matching)
    '''

    planei = int(satA.in_plane)
    planej = int(satB.in_plane)

    if planei == planej:
        if satA.latitude < satB.latitude:
            return 1
        else:
            return 2
    if(abs(satA.longitude - satB.longitude) < math.pi): # they are not too far away
        if satA.longitude < satB.longitude:
            return 3
        else:
            return 4
    else:                                                       # they are very far away
        if satA.longitude > satB.longitude:
            return 3
        else:
            return 4


def linkedSatsList(g):
    '''
    This funtion retunrs a dictionary (Gateway: linekdSatellite)
    '''
    linkedSats = []
    for node in g.nodes:
        if not node[0].isdigit():
            linkedSats.append(list(g.edges(node))[0])
    return pd.DataFrame(linkedSats)


def getDestination(Block, g, sat = None):
    '''
    Returns:
    blockDestination: Position of the satellite linked to the block destination Gateway among a list of all the
                      satellites linked to Gateways
    linkedGateway:    If the satellite provided is linked to a gateway, it will return the position of the satellite in
                      the mentioned list. Otherwise it will return -1.
    '''
    destination = list(g.edges(Block.destination.name))[0][1]    # ID of the Satellite linked to the block destination GT
    blockDestination = (linkedSatsList(g)[1] == destination).argmax()

    if sat is None:
        return blockDestination
    else:
        satDest = Block.destination.linkedSat[1]
        return getGridPosition(GridSize, [tuple([math.degrees(satDest.latitude), math.degrees(satDest.longitude), satDest.ID])], False, False)[0]


def getlinkedSats(satA, g, earth):
    '''
    Given a satellite the function will return a list with the linked satellite at each direction.
    If that direction has no linked satellite, it will be None
    At the graph each edge is a satA, satB pair with properties like dirij or dirji, i will always
    be the satellite of the lowest plane and 1 will be righ direction (East).

    SAT UP:      northest linked satellite
    SAT DOWN:    southest linked satellite
    SAT LEFT:    linked satellite with lower  plane ID
    SAT RIGHT:   linked satellite with higher plane ID
    '''
    linkedSats = {'U':None, 'D':None, 'R':None, 'L':None}
    for edge in list(g.edges(satA.ID)):
        if edge[1][0].isdigit():
            satB = findByID(earth, edge[1])
            dir = getDirection(satA, satB)

            if(dir == 1 and linkedSats['U'] is None):               # Found a satellite at north
                linkedSats['U']  = satB
            elif(dir == 1):                                         # Found second North, this sat is on South Pole
                if satB.latitude > linkedSats['U'].latitude:
                    # the satellite seen is more at north than Up one, so is set as new Up
                    linkedSats['D'] = linkedSats['U']
                    linkedSats['U'] = satB
                else:
                    # the satellite seen is less at north than Up one, so is set as Down
                    linkedSats['D'] = satB

            elif(dir == 2 and linkedSats['D'] is None):             # Found satellite at South
                linkedSats['D']  = satB   
            elif(dir == 2):                                         # Found second Down, this sat is on North Pole
                if satB.latitude < linkedSats['D'].latitude:        
                    linkedSats['U'] = linkedSats['D']
                    linkedSats['D'] = satB
                else:
                    linkedSats['U'] = satB

            elif(dir == 3):                                         # Found Satellite at East
                linkedSats['R']  = satB
            elif(dir == 4):                                         # Found Satellite at West
                linkedSats['L']  = satB

        else:
            pass
    return linkedSats


def getState(Block, satA, g, earth):
    '''
    Given a dataBlock and the current satellite this function will return a list with the 
    values of the 5 fields of the state space.
    Destination: linked satellite to the destination gateway index.

    we initialize the score of the satellites in 2 (worst case) because we do not know if they 
    will actually have a linked satellite in that direction.
    If they have it the satellite score will replace the initialization score (2) but if they dont 
    have it, as we need a score in order to set the state space we will give the worst score and
    send a None in the destinations dict. That action will be initialized with -infinite in the QTable
    '''
    destination  = getDestination(Block, g)
    state        = [2, 2, 2, 2, destination]   

    state[0] = getSatScore(satA, satA.QLearning.linkedSats['U'], g)
    state[1] = getSatScore(satA, satA.QLearning.linkedSats['D'], g)
    state[2] = getSatScore(satA, satA.QLearning.linkedSats['R'], g)
    state[3] = getSatScore(satA, satA.QLearning.linkedSats['L'], g)

    return state


def getBiasedlatitude(sat):
    try:
        return (int(math.degrees(sat.latitude))+90)#/180
    except AttributeError as e:
        # print(f"getBiasedlatitude Caught an exception: {e}")
        return -1


def getBiasedLongitude(sat):
    try:
        return (int(math.degrees(sat.longitude))+180)#/360
    except AttributeError as e:
        # print(f"getBiasedLongitude Caught an exception: {e}")
        return -1
    

def getDeepState(block, sat, linkedSats):
    satDest = block.destination.linkedSat[1]
    if satDest is None:
        print(f'{block.destination} has no linked satellite :(')
        return None

    queuesU = getQueues(linkedSats['U'], DDQN = True)
    queuesD = getQueues(linkedSats['D'], DDQN = True)
    queuesR = getQueues(linkedSats['R'], DDQN = True)
    queuesL = getQueues(linkedSats['L'], DDQN = True)
    return np.array([getDeepSatScore(queuesU['U']),                             # Up link scores
                    getDeepSatScore(queuesU['D']),
                    getDeepSatScore(queuesU['R']),
                    getDeepSatScore(queuesU['L']),
                    getBiasedlatitude(linkedSats['U']),                         # Up link Positions
                    getBiasedLongitude(linkedSats['U']),
                    getDeepSatScore(queuesD['U']),                              # Down link scores
                    getDeepSatScore(queuesD['D']),
                    getDeepSatScore(queuesD['R']),
                    getDeepSatScore(queuesD['L']),
                    getBiasedlatitude(linkedSats['D']),                         # Dpwn link Positions
                    getBiasedLongitude(linkedSats['D']),
                    getDeepSatScore(queuesR['U']),                              # Right link scores
                    getDeepSatScore(queuesR['D']),
                    getDeepSatScore(queuesR['R']),
                    getDeepSatScore(queuesR['L']),
                    getBiasedlatitude(linkedSats['R']),                         # Right link Positions
                    getBiasedLongitude(linkedSats['R']),
                    getDeepSatScore(queuesL['U']),                              # Left link scores
                    getDeepSatScore(queuesL['D']),
                    getDeepSatScore(queuesL['R']),
                    getDeepSatScore(queuesL['L']),
                    getBiasedlatitude(linkedSats['L']),                         # Left link Positions
                    getBiasedLongitude(linkedSats['L']),

                    int(math.degrees(sat.latitude))+90,                         # Actual Latitude
                    int(math.degrees(sat.longitude))+180,                       # Actual Longitude
                    int(math.degrees(satDest.latitude))+90,                     # Destination Latitude
                    int(math.degrees(satDest.longitude))+180]).reshape(1,-1)    # Destination Longitude
    

def getDeepStateGrid(block, sat, g):
    '''
    DEPRECATED. Use getGridPosition in getdeepstate

    Given a dataBlock and the current satellite this function will return a list with the values of the 7 fields of the state space.
    The model will have as many INPUT neurons as fields the state space has:
    SatUp    Queue:     Will be the queue length of that satellite. If it has no link there, it will be -1.
    SatDown  Queue:     Will be the queue length of that satellite. If it has no link there, it will be -1.
    SatLeft  Queue:     Will be the queue length of that satellite. If it has no link there, it will be -1.
    SatRight Queue:     Will be the queue length of that satellite. If it has no link there, it will be -1.
    Grid Position:      Will be the position inside a global grid
    Block Destination:  Will be the position of the satellite linked to the block destination Gateway among a list of all the satellites linked to a GT.
    Linked Gateway:     Will be -1 if the satellite is not linked to any Gateway
    '''
    blockDestination = getDestination(block, g, sat = sat) 
    gridPos = getGridPosition(GridSize, [tuple([math.degrees(sat.latitude), math.degrees(sat.longitude), sat.ID])], False, False)[0] 

    return np.array([gridPos, blockDestination]).reshape(1,-1)


# def getGridPosition(n: int, locations: List[Tuple([float, float, str])], draw = False, bigGrid = False):
def getGridPosition(n: int, locations, draw = False, bigGrid = False):
    '''
    Given:
    n           -> the granularity of the grid. 2n will be the number of squares that the earh has per row.
    locations   -> a list of [longitude, latitude] pairs to map
    draw        -> a flag. If it is up it draws the map and saves it
    bigGrid     -> a flag. If it is up it prints the draws the map grid. If it is down it just draws rectangles with the positions.
    
    Returns:
    A list with all the positions of the provided [longitude, latitude] pairs
    I the flags are up, a map with the pairs pointed on the map.
    '''
    # Calculate the size of each square
    square_size = 180 / n
    
    # Create the map
    m = folium.Map(location=[0, 0], zoom_start=2)
    positions = []
    
    # Add the rectangles and markers for the specified locations to the map
    for latitude, longitude, name in locations:
        # Determine the position of the location in the grid
        x_pos = int((longitude + 180) // square_size)
        y_pos = int((latitude + 90) // square_size)
        
        # Calculate the position of the object in the grid
        position = x_pos + (y_pos * (360//square_size))
        positions.append(position)

        # Add the rectangle to the map
        if draw:
            folium.Rectangle(
                bounds=[[y_pos * square_size - 90, x_pos * square_size - 180], [(y_pos + 1) * square_size - 90, (x_pos + 1) * square_size - 180]],
                color='red',
                fill=True
            ).add_to(m)

            # Add the marker and pop-up to the map
            folium.Marker(location=[latitude, longitude], popup=folium.Popup(f'Position: {position}')).add_to(m)
            folium.map.Marker([latitude, longitude],
            icon=folium.features.DivIcon(
            icon_size=(250,36),
            icon_anchor=(0,0),
            html='<div style="font-size: 10pt; font-weight:bold; color: black;">[' + name + ': ' + str(position) +']</div>',
            )).add_to(m)

        # Add the grid to the map
        if bigGrid:
            for i in range(-90, 90):
                for j in range(-180, 180):
                    folium.Rectangle(
                        bounds=[[i * square_size, j * square_size], [(i + 1) * square_size, (j + 1) * square_size]],
                        color='red',
                        fill=True
                    ).add_to(m)
    # Display the map
    if(draw):
        display(m)
        m.save('map' + str(n) + '.html')

    total_cells = (360//square_size) * (180//square_size)
    return positions


def createQTable(NGT):
    '''
    Create a 6D numpy array to hold the current Q-values for each state and action pair: Q(s, a)
    The array contains 5 dimensions with the shape of the environment, as well as a 6th "action" dimension.
    The "action" dimension consists of 4 layers that will allow us to keep track of the Q-values for each possible action in each state
    The value of each (state, action) pair is initialized to 0.
    '''

    actions = ('N', 'S', 'E', 'W')
    satUp, satDown, satRight, satLeft = 3, 3, 3, 3
    Destination = NGT

    qValues = np.zeros((satUp, satDown, satRight, satLeft, Destination, len(actions)))  # first 5 fields are states while 6th field is the action. 4050 values with 10 GTs

    return qValues


###############################################################################
##########################   Q-Learning - Rewards    ##########################
###############################################################################


# @profile
def getSlantRange(satA, satB):
    '''
    given 2 satellites, it will return the slant range between them (With the method used at 'get_slant_range_optimized')
    '''
    return np.linalg.norm(np.array((satA.x, satA.y, satA.z)) - np.array((satB.x, satB.y, satB.z)))  # posA - posB


# @profile
def getQueueReward(queueTime, w1):
    '''
    Given the queue time in seconds, this function will return the queue reward.
    With 125 packets, 9ms Queue (The thershold that we take to consider a queue as high) the reward will be -0.04 (with w1 = 2)
    '''
    return w1*(1-10**queueTime)


# @profile
def getDistanceReward(satA, satB, destination, w2):
    '''
    This function will return the instant reward regarding to the slant range reduction from actual node to destination
    just after the agent takes an action (destination is the satellite linked to the destination Gateway)

    TSLa: Total slant range from sat A to destination
    TSLb: Total slant range from sat B to destination
    SLR : Slant Range reduction after taking the action (Going from satA to satB)

    Formula: w*(SLR + TSLa)/TSLa = w*(TSLa - TSLb + TSLa)/TSLa = w*(2*TSLa - TSLb)/TSLa
    '''
    balance   = -1      # centralizes the result in 0

    TSLa = getSlantRange(satA, destination)
    TSLb = getSlantRange(satB, destination)
    return w2*((2*TSLa-TSLb)/TSLa + balance)


def getDistanceRewardV2(sat, nextSat, satU, satD, satR, satL, destination, w2):
    '''
    Computes the reward by comparing how closer you get to the destination in terms of KM (SLr, Slant Range Reduction) with the
    average distance with all your neighbours (SLav, Slant Range average)
    If any of the linked satellites is not available, it is handled
    SLr/SLav + balance
    '''

    SLr = getSlantRange(sat, destination) - getSlantRange(nextSat, destination)
    SLU = SLD = SLR = SLL = 0
    count = 0

    # Calculate slant range for each satellite, if it is not None
    if satU is not None:
        SLU = getSlantRange(satU, sat)
        count += 1
    if satD is not None:
        SLD = getSlantRange(satD, sat)
        count += 1
    if satR is not None:
        SLR = getSlantRange(satR, sat)
        count += 1
    if satL is not None:
        SLL = getSlantRange(satL, sat)
        count += 1

    SLav = (SLU + SLD + SLR + SLL) / count if count > 0 else 0

    return w2 * (SLr / SLav) if SLav != 0 else 0


def getDistanceRewardV3(sat, nextSat, satU, satD, satR, satL, destination, w2):
    '''
    Returns the distance reward computed by comparing how closer you get to the destination in terms of KM (SLr, Slant Range Reduction) with
    how close you could get as maximum taking the other options going to any of the other neighbours (max(SLrs), max(Slant range reductions from all the neighbours))
    reward = SLr/max(SLs)
    '''
    SLr = getSlantRange(sat, destination) - getSlantRange(nextSat, destination)
    SLrs= []

    if satU is not None:
        SLrs.append(getSlantRange(sat, destination) - getSlantRange(satU, destination))
    if satD is not None:
        SLrs.append(getSlantRange(sat, destination) - getSlantRange(satD, destination))
    if satR is not None:
        SLrs.append(getSlantRange(sat, destination) - getSlantRange(satR, destination))
    if satL is not None:
        SLrs.append(getSlantRange(sat, destination) - getSlantRange(satL, destination))

    return w2*SLr/max(SLrs)
    

def getDistanceRewardV4(sat, nextSat, destination, w2):
    SLr = getSlantRange(sat, destination) - getSlantRange(nextSat, destination)
    return w2*SLr/1000000


def saveHyperparams(outputPath, inputParams, hyperparams):
    print('Saving hyperparams at: ' + str(outputPath))
    hyperparams = ['Constellation: ' + str(inputParams['Constellation'][0]),
                'Import QTables: ' + str(hyperparams.importQ),
                'printPath: ' + str(hyperparams.printPath),
                'Test length: ' + str(inputParams['Test length'][0]),
                'Alpha: ' + str(hyperparams.alpha),
                'Gamma: ' + str(hyperparams.gamma),
                'Epsilon: ' + str(hyperparams.epsilon), 
                'Max epsilon: ' + str(hyperparams.MAX_EPSILON), 
                'Min epsilon: ' + str(hyperparams.MIN_EPSILON), 
                'Arrive Reward: ' + str(hyperparams.ArriveR), 
                'w1: ' + str(hyperparams.w1), 
                'w2: ' + str(hyperparams.w2),
                'Update freq: ' + str(hyperparams.updateF),
                'Batch Size: ' + str(hyperparams.batchSize),
                'Buffer Size: ' + str(hyperparams.bufferSize),
                'Hard Update: ' + str(hyperparams.hardUpdate),
                'Exploration: ' + str(explore)]

    # save hyperparams
    with open(outputPath + 'hyperparams.txt', 'w') as f:
        for param in hyperparams:
            f.write(param + '\n')


def saveQTables(outputPath, earth):
    print('Saving Q-Tables at: ' + outputPath)
    # create output path if it does not exist
    path = outputPath + 'qTablesExport_ ' + str(len(earth.gateways)) + 'GTs/'
    os.makedirs(path, exist_ok=True) 

    # save Q-Tables
    for plane in earth.LEO:
        for sat in plane.sats:
            qTable = sat.QLearning.qTable
            with open(path + sat.ID + '.npy', 'wb') as f:
                np.save(f, qTable)


def saveDeepNetworks(outputPath, earth):
    print('Saving Deep Neural networks at: ' + outputPath)
    earth.DDQNA.qNetwork.save(outputPath + 'qNetwork_'+ str(len(earth.gateways)) + 'GTs' + '.h5')


###############################################################################
#########################    Simulation && Results    #########################
###############################################################################


def plotLatenciesBars(percentages, outputPath):
    '''
    Bar plot where each bar is a scenario with a different nº of gateways and where each color represents one of the three latencies.
    '''
    # plot percent stacked barplot
    barWidth= 0.85
    r       = percentages['GTnumber']
    numbers = percentages['GTnumber']
    GTnumber= len(r)

    plt.bar(r, percentages['Propagation time'], color='#b5ffb9', edgecolor='white', width=barWidth, label="Propagation time")   # Propagation time
    plt.bar(r, percentages['Queue time'], bottom=percentages['Propagation time'], color='#f9bc86',                              # Queue time
             edgecolor='white', width=barWidth, label="Queue time")
    plt.bar(r, percentages['Transmission time'], bottom=[i+j for i,j in zip(percentages['Propagation time'],                    # Tx time
            percentages['Queue time'])], color='#a3acff', edgecolor='white', width=barWidth, label="Transmission time")

    # Custom x axis
    plt.xticks(numbers)
    plt.xlabel("Nº of gateways")
    plt.ylabel('Latency')

    # Add a legend
    plt.legend(loc='lower left')

    # Show and save graphic
    plt.savefig(outputPath + 'Percentages_{}_Gateways.png'.format(GTnumber+1))
    plt.close()
    # plt.show()


def plotQueues(queues, outputPath, GTnumber):
    '''
    Will plot the cumulative distribution function (CDF) and probability density function (PDF) of all the queues that each package has faced.
    ''' 
    os.makedirs(outputPath + '/pngQueues/', exist_ok=True) # create output path
    plt.hist(queues, bins=max(queues), cumulative=True, density = True, label='CDF DATA', histtype='step', alpha=0.55, color='blue')
    plt.xlabel('Queue length')
    plt.legend(loc = 'lower left')
    plt.savefig(outputPath + '/pngQueues/' + 'Queues_{}_Gateways.png'.format(GTnumber))
    plt.close()
    d = pd.DataFrame(queues)
    d.to_csv(outputPath + '/csv/' + "Queues_{}_Gateways.csv".format(GTnumber), index = False)


def extract_block_index(block_id):
    return int(block_id.split('_')[-1])


def save_epsilons(outputPath, eps, GTnumber):
    epsilons = [x[0] for x in eps]
    times    = [x[1] for x in eps]
    plt.plot(times, epsilons)
    plt.title("Epsilon over Time")
    plt.xlabel("Time (s)")
    plt.ylabel("Epsilon")
    os.makedirs(outputPath + '/epsilons/', exist_ok=True) # create output path
    plt.savefig(outputPath + '/epsilons/' + "epsilon_{}_gateways.png".format(GTnumber))
    plt.close()

    data = {'epsilon': [e for e in epsilons], 'time': [t for t in times]}
    df = pd.DataFrame(data)
    os.makedirs(outputPath + '/csv/' , exist_ok=True) # create output path
    df.to_csv(outputPath + '/csv/' + "epsilons_{}_gateways.csv".format(GTnumber), index=False)

    return df
    

def save_losses(outputPath, earth1, GTnumber):
    losses = [x[0] for x in earth1.loss]
    times  = [x[1] for x in earth1.loss]
    plt.plot(times, losses)
    plt.xlabel("Time (s)")
    plt.ylabel("Loss")
    plt.title("Loss over Time")
    os.makedirs(outputPath + '/loss/', exist_ok=True) # create output path
    plt.savefig(outputPath + '/loss/' + "loss_{}_gatewaysTime.png".format(GTnumber))
    plt.close()

    data = {'loss': [l for l in losses], 'time': [t for t in times]}
    df = pd.DataFrame(data)
    df.to_csv(outputPath + '/csv/' + "loss_{}_gateways.csv".format(GTnumber), index=False)
    os.makedirs(outputPath + '/loss/', exist_ok=True) # create output path

    xs = [l for l in range(len(losses))]
    plt.plot(xs, losses)
    plt.xlabel("Steps")
    plt.ylabel("Loss")
    plt.title("Loss over Steps")
    plt.savefig(outputPath + '/loss/' + "loss_{}_gatewaysSteps.png".format(GTnumber))
    plt.close()

    # save losses average
    plt.plot(range(len(earth1.lossAv)), earth1.lossAv)
    plt.xlabel("Steps")
    plt.ylabel("Loss average")
    plt.title("Loss average over Steps")
    os.makedirs(outputPath + '/loss/', exist_ok=True) # create output path
    plt.savefig(outputPath + '/loss/' + "loss_{}_gatewaysAverage.png".format(GTnumber))
    plt.close()


def plotSavePathLatencies(outputPath, GTnumber, pathBlocks):
    # figure of latencies between two first gateways
    latency = []
    arrival = []
    for item in pathBlocks[0]:
        latency.append(item[0])
        arrival.append(item[1])
    plt.scatter(arrival, latency, c='r')
    plt.xlabel("Time")
    plt.ylabel("Latency")
    os.makedirs(outputPath + '/pngLatencies/', exist_ok=True) # create output path
    plt.savefig(outputPath + '/pngLatencies/' + '{}_gatewaysTime.png'.format(GTnumber))
    plt.close()

    # x axis is the number of the arrival, not the time
    xs = [l for l in range(len(latency))]
    plt.figure()
    plt.scatter(xs,latency, c='r')
    plt.xlabel("Arrival index")
    plt.ylabel('Latency')
    plt.savefig(outputPath + '/pngLatencies/' + '{}_gateways.png'.format(GTnumber))
    plt.close()

    # Save latencies
    os.makedirs(outputPath + '/csv/', exist_ok=True) # create output path
    data = {'Latency': [l for l in latency], 'Arrival Time': [t for t in arrival]}
    df = pd.DataFrame(data)
    df.to_csv(outputPath + '/csv/' + "pathLatencies_{}_gateways.csv".format(GTnumber), index=False)
    os.makedirs(outputPath + '/loss/', exist_ok=True) # create output path


def plotSaveAllLatencies(outputPath, GTnumber, allLatencies, epsDF=None, annotate_min_latency=True):  
    # preprocess and setup
    sns.set(font_scale=1.5)
    window_size = winSize
    marker_size = markerSize
    df = pd.DataFrame(allLatencies, columns=['Creation Time', 'Latency', 'Arrival Time', 'Source', 
                                             'Destination', 'Block ID', 'QueueTime', 'TxTime', 'PropTime'])
    df['Block Index'] = df['Block ID'].apply(extract_block_index)
    df = df.sort_values(by=['Source', 'Destination', 'Block Index'])
    df.to_csv(outputPath + '/csv/' + "allLatencies_{}_gateways.csv".format(GTnumber))

    # Convert time values to milliseconds
    df['Creation Time'] *= 1000
    df['Arrival Time']  *= 1000
    df['Latency']       *= 1000
    if epsDF is not None:
        epsDF['time']   *= 1000

    # Calculate the rolling average for each unique path
    df['Path'] = df['Source'].astype(str) + ' -> ' + df['Destination'].astype(str)
    df['Latency_Rolling_Avg'] = df.groupby('Path')['Latency'].transform(lambda x: x.rolling(window=window_size).mean())
    
    # Metrics for x-axis
    metrics = ['Arrival Time', 'Creation Time']

    # Create subplots
    fig, axes = plt.subplots(len(metrics), 2, figsize=(18, 18))

    for i, metric in enumerate(metrics):
        # Line Plots on the left (column index 0)
        lineplot = sns.lineplot(x=metric, y='Latency_Rolling_Avg', hue='Path', ax=axes[i, 0], data=df)
        axes[i, 0].set_title(f'Latency Trends Over {metric} (Window Size = {window_size})')
        axes[i, 0].set_xlabel(metric + ' (ms)')
        axes[i, 0].set_ylabel('Average Latency (ms)')

        # Annotate minimum latency for Creation Time only
        if annotate_min_latency and metric == 'Creation Time':
            unique_paths = df['Path'].unique()
            for path in unique_paths:
                df_path = df[df['Path'] == path]
                min_latency = df_path['Latency_Rolling_Avg'].min()
                min_pos = df_path[metric][df_path['Latency_Rolling_Avg'].idxmin()]
                axes[i, 0].annotate(f'{min_latency:.0f} ms', xy=(min_pos, min_latency), 
                                    xytext=(-50, 30), textcoords='offset points', 
                                    arrowprops=dict(arrowstyle='->', color='black'))

        # Scatter Plots on the right (column index 1)
        scatterplot = sns.scatterplot(x=metric, y='Latency', hue='Path', ax=axes[i, 1], data=df, marker='o', s=marker_size)
        axes[i, 1].set_title(f'Individual Latency Points Over {metric}')
        axes[i, 1].set_xlabel(metric)
        axes[i, 1].set_ylabel('Latency')

        # Create a twin y-axis for epsilon data if epsDF is not None
        if epsDF is not None:
            ax2 = axes[i, 0].twinx()
            line3 = sns.lineplot(x='time', y='epsilon', data=epsDF, color='purple', label='Epsilon', ax=ax2)

            # Merge legends
            handles1, labels1 = axes[i, 0].get_legend_handles_labels()
            handles2, labels2 = ax2.get_legend_handles_labels()
            axes[i, 0].legend(handles1 + handles2, labels1 + labels2, loc='upper right')
            ax2.get_legend().remove()
        else:
            # Handle legend for the case when epsDF is None
            handles, labels = axes[i, 0].get_legend_handles_labels()
            axes[i, 0].legend(handles, labels, loc='upper right')
        
    # Adjust the layout
    plt.tight_layout()
    os.makedirs(outputPath + '/pngAllLatencies/', exist_ok=True) # create output path
    plt.savefig(outputPath + '/pngAllLatencies/' + '{}_gateways_All_Latencies_subplots.png'.format(GTnumber), dpi = 300)
    plt.close()
    sns.set()


def plotRatesFigures():
    values = [upGSLRates, downGSLRates, interRates, intraRate]

    plt.figure()
    plt.hist(np.asarray(interRates)/1e9, cumulative=1, histtype='step', density=True)
    plt.title('CDF - Inter plane ISL data rates')
    plt.ylabel('Empirical CDF')
    plt.xlabel('Data rate [Gbps]')
    plt.show()
    plt.close()

    plt.figure()
    plt.hist(np.asarray(upGSLRates)/1e9, cumulative=1, histtype='step', density=True)
    plt.title('CDF - Uplink data rates')
    plt.ylabel('Empirical CDF')
    plt.xlabel('Data rate [Gbps]')
    plt.show()
    plt.close()

    plt.figure()
    plt.hist(np.asarray(downGSLRates)/1e9, cumulative=1, histtype='step', density=True)
    plt.title('CDF - Downlink data rates')
    plt.ylabel('Empirical CDF')
    plt.xlabel('Data rate [Gbps]')
    plt.show()
    plt.close()

# @profile
def RunSimulation(GTs, inputPath, outputPath, populationData, radioKM):
    start_time = datetime.now()
    '''
    this is required for the bar plot at the end of the simulation
    percentages = {'Queue time': [],
                'Propagation time': [],
                'Transmission time': [],
                'GTnumber' : []}
    '''
    inputParams = pd.read_csv(inputPath + "inputRL.csv")

    locations = inputParams['Locations'].copy()
    print('Nº of Gateways: ' + str(len(locations)))

    # pathing     = inputParams['Pathing'][0]
    testType    = inputParams['Test type'][0]
    testLength  = inputParams['Test length'][0]
    # numberOfMovements = 0

    print('Routing metric: ' + pathing)

    simulationTimelimit = testLength if testType != "Rates" else movementTime * testLength + 10

    firstGT = True
    for GTnumber in GTs:
        global CurrentGTnumber
        global nnpath
        global Train
        global TrainThis
        TrainThis       = Train
        CurrentGTnumber = GTnumber
        
        if firstGT:
            nnpath  = f'./pre_trained_NNs/qNetwork_1GTs.h5'
            firstGT = False
        else:
            nnpath  = f'{outputPath}/NNs/qNetwork_{GTnumber-1}GTs.h5'

        env = simpy.Environment()

        if mixLocs: # changes the selected GTs every iteration
            random.shuffle(locations)
        inputParams['Locations'] = locations[:GTnumber]
        print('----------------------------------')
        print('Time:')
        print(datetime.now().strftime("%H:%M:%S"))
        print('Locations:')
        print(inputParams['Locations'][:GTnumber])
        print(f'Movement Time: {movementTime}')
        print(f'Rotation Factor: {ndeltas}')
        print(f'Minimum epsilon: {MIN_EPSILON}')
        print(f'Reward for deliver: {ArriveReward}')
        print(f'Stop Loss: {stopLoss}, number of samples considered: {nLosses}, threshold: {lThreshold}')
        print('----------------------------------')
        earth1, _, _, _ = initialize(env, populationData, inputPath + 'Gateways.csv', radioKM, inputParams, movementTime, locations, outputPath)
        earth1.outputPath = outputPath

        progress = env.process(simProgress(simulationTimelimit, env))
        startTime = time.time()
        env.run(simulationTimelimit)
        timeToSim = time.time() - startTime

        if testType == "Rates":
            plotRatesFigures()

        else:
            results, allLatencies, pathBlocks = getBlockTransmissionStats(timeToSim, inputParams['Locations'], inputParams['Constellation'][0], earth1)
            print(f'DataBlocks lost: {earth1.lostBlocks}')
            
            # save & plot ftirst 2 GTs path latencies
            plotSavePathLatencies(outputPath, GTnumber, pathBlocks)
            
            if pathing == "Deep Q-Learning" or pathing == 'Q-Learning':
                eps = earth1.DDQNA.epsilon if pathing == "Deep Q-Learning" else earth1.epsilon
                # save epsilons
                epsDF = save_epsilons(outputPath, eps, GTnumber)

                # save & plot all paths latencies
                plotSaveAllLatencies(outputPath, GTnumber, allLatencies, epsDF)
            
            elif pathing == "Deep Q-Learning":
                # save losses
                save_losses(outputPath, earth1, GTnumber)
                
            else:
                plotSaveAllLatencies(outputPath, GTnumber, allLatencies)

        plotShortestPath(earth1, pathBlocks[1][-1].path, outputPath)
        plotQueues(earth1.queues, outputPath, GTnumber)

        print(f"number of gateways: {GTnumber}")
        print('Path:')
        print(pathBlocks[1][-1].path)
        print('Bottleneck:')
        print(findBottleneck(pathBlocks[1][-1].path, earth1))
        '''
        # add data for percentages bar plot
        # percentages['Queue time']       .append(results.meanQueueLatency)
        # percentages['Propagation time'] .append(results.meanPropLatency)
        # percentages['Transmission time'].append(results.meanTransLatency)
        # percentages['GTnumber']         .append(GTnumber)
        '''
        '''
        # save congestion test data
        blocks = []
        for block in receivedDataBlocks:
            blocks.append(BlocksForPickle(block))
        blockPath = f"./Results/Congestion_Test/{pathing} {float(pd.read_csv('inputRL.csv')['Test length'][0])}/"
        os.makedirs(blockPath, exist_ok=True)
        try:
            np.save("{}blocks_{}".format(blockPath, GTnumber), np.asarray(blocks),allow_pickle=True)
        except pickle.PicklingError:
            print('Error with pickle and profiling')
            '''

        # save learnt values
        if pathing == 'Q-Learning':
            saveQTables(outputPath, earth1)
        elif pathing == 'Deep Q-Learning':
            saveDeepNetworks(outputPath + '/NNs/', earth1)

        # percentages.clear()
        receivedDataBlocks  .clear()
        createdBlocks       .clear()
        pathBlocks          .clear()
        allLatencies        .clear()
        upGSLRates          .clear()
        downGSLRates        .clear()
        interRates          .clear()
        intraRate           .clear()
        del results
        del earth1
        del env
        del _
        gc.collect()

    # plotLatenciesBars(percentages, outputPath)

    print('----------------------------------')
    print('Time:')
    end_time = datetime.now()
    print(end_time.strftime("%H:%M:%S"))
    print('----------------------------------')
    elapsed_time = end_time - start_time
    print(f"Elapsed time: {elapsed_time}")
    print('----------------------------------')


###############################################################################
##############################     Main     ###################################
###############################################################################


if __name__ == '__main__':
    os.makedirs(outputPath, exist_ok=True) 
    sys.stdout = Logger(outputPath + 'logfile.log')

    RunSimulation(GTs, './', outputPath, populationMap, radioKM=rKM)
    # cProfile.run("RunSimulation(GTs, './', outputPath, populationMap, radioKM=rKM)")
