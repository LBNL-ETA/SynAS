import os
import logging
import numpy as np
import pandas as pd

try:
    root = os.path.dirname(os.path.abspath(__file__))
except:
    root = os.getcwd()

class dispatcher(object):
    def __init__(self, length=60*60, step=4, reg_up=True, reg_dn=True, seed=None,
                 db=os.path.join(os.path.dirname(root), 'data', 'FrequencyRegulationData.csv')):
        '''
        The dispatcher class to generate infinitive sequency of fast frequency regulation signal.

        Input
        -----
        length (int): Total length of sequence, in seconds. (default = 60*60)
        step (int): Stepsize of sequence, in seconds. (default = 4)
            NOTE: Only 4 second steps supported in this version. Any other value will raise 
            a warning and fallback to the default.
        reg_up (bool): Generate dispatch for regulation up (power feedback to grid). (default = True)
            NOTE: Only True supported in this version. Any other value will raise 
            a warning and fallback to the default.
        reg_dn (bool): Generate dispatch for regulation down (power draw to grid). (default = True)
            NOTE: Only True supported in this version. Any other value will raise 
            a warning and fallback to the default.
        seed (int): Seed for sequence generation. (default = None)
        db (str): Path to database file. (default = __file__\..\data\FrequencyRegulationData.csv)        
        '''
        self.logger = logging.getLogger(__name__)
        self.length = length
        self.step = step
        self.reg_up = reg_up
        self.reg_dn = reg_dn
        self.seed = seed
        self.db = db
        
        # Check inputs
        if not step == 4:
            self.logger.warning('The "step" argument must be int(4) in this version. Fallback to 4.')
            self.step = 4
        if not self.reg_up:
            self.logger.warning('The "reg_up" argument must be True in this version. Fallback to True.')
            self.reg_up = True
        if not self.reg_dn:
            self.logger.warning('The "reg_dn" argument must be True in this version. Fallback to True.')
            self.reg_dn = True

        # Add variables
        self.time = 0
        self.root = root        

        # Read the datafile
        self.data = self.read_data()
        
        # Generate sequence
        self.seq = self.generate_seq()
        
    def read_data(self):
        '''
        Reads and processes the database file specified as "db" argument.
        '''
        if not os.path.exists(self.db):
            msg = 'Cannot locate file "{}".'.format(self.db)
            self.logger.error(msg)
            raise FileNotFoundError(msg)
        data = pd.read_csv(self.db, index_col=[0])
        data = data.reset_index(drop=True)
        data.index = data.index * self.step / (60*60)
        
        # Cut into hourly
        res = pd.DataFrame()
        for c in data:
            t = data[c]
            for h in range(int(t.index[-1] + 0.5)):
                res['{}_{}'.format(c, h)] = t.loc[h:(h+1-1e-4)].values
        return res
    
    def generate_seq(self):
        '''
        Generates a regulaiton dispatch sequence of length defined by the "length" argument.
        '''
        np.random.seed(self.seed)
        len_seq = int(self.length/self.step)
        n_samples = int(self.length/self.step / len(self.data) + 0.5) * 100
        samples = np.random.randint(0, len(self.data.columns), n_samples)
        d = pd.DataFrame()
        len_d = 0
        i = 0
        while len_d < len_seq:
            if (n_samples - 1) < i:
                self.logger.error('Could not assemble dispatch signal with seed {}.'.format(self.seed) + \
                                  ' Please try another seed.')
                return pd.DataFrame()
            if d.empty:
                d = self.data.iloc[:,samples[i]]
            else:
                last_val = d.iloc[-1]
                new_sample = self.data.iloc[:,samples[i]]
                if last_val in new_sample.values:
                    ix_start = new_sample[new_sample == last_val].index[0]
                    d = d.append(new_sample.loc[ix_start:])
            len_d = len(d)
            i += 1
        self.i = i
        d = d[:len_seq]
        d = d.reset_index(drop=True)
        d.index = d.index * self.step
        
        # Check statistics
        stats_data = self.data.describe().loc['mean'].describe()[['50%','75%']].to_dict()
        if not (d.describe()['mean'] <= stats_data['75%']) or \
            not (d.describe()['mean'] >= stats_data['50%']):
            self.logger.warning('Mean of sequence out of range, please use another seed or increase sequence length.')
        return d
    
    def do_step(self):
        '''
        Function to iterate through regulation dispatch in a co-simulation environment. 
        
        Each function call integrates time by one step, defined by the "step" argument.
        
        Return
        ------
        Return is a list, with same order as arguments below.
        time (float): Current timestep since start of sequence, in seconds.
        dispatch (float): Value of dispatch, in kW.
        '''
        time_now = float(self.time)
        self.time += self.step
        return [time_now, self.seq[time_now]]
    
    def get_sequence(self, timestamp=None):
        '''
        Function to generate a batch sequence of regulation dispatch. 
        
        Input
        -----
        timestamp (str): Selector of timestamp format, one of [None, "hour", "minute"]. (default = None)
        
        Return
        ------
        res (pd.Series): The regulation dispatch with timestamp as index, and dispatch as value.
        '''
        res = self.seq.copy(deep=True)
        res.name = 'Dispatch [kW]'
        res.index.name = 'Time [s]'
        if timestamp:
            if timestamp == 'hour':
                res.index = res.index / (60*60)
                res.index.name = 'Time [h]'
            elif timestamp == 'minute':
                res.index = res.index / (60)
                res.index.name = 'Time [min]'
            else:
                msg = 'The defined "timestamp" as "{}" is invalid. '.format(timestamp)
                msg += 'Please use one of: [None, "hour", "minute"].'
                self.logger.error(msg)
                raise ValueError(msg)
        return res
    
if __name__ == '__main__':
    seed = 20
    dispatch = dispatcher(seed=seed)
    print('Regulation Dispatch for 1 minute:\n')
    print(pd.DataFrame(dispatch.get_sequence(timestamp='minute').loc[:1]))