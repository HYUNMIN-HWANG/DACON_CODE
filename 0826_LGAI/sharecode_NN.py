import random
import os

import numpy as np
import pandas as pd
from torch import optim
import torch

import torch.nn as nn
from torch.nn.modules.container import Sequential

from tqdm import tqdm

import gc

class CFG:
    dataPath = 'D:\\Data\\LGAI_AutoDriveSensors\\'
    trainPath = dataPath+'train.csv'
    testPath = dataPath+'test.csv'
    submission = dataPath+'sample_submission.csv'
    outPath = dataPath+'submit/'
    weightsavePath = dataPath+'weights/'
    
    device = 'cuda'
    
def seedEverything(random_seed):
    torch.manual_seed(random_seed)
    torch.cuda.manual_seed(random_seed)
    torch.cuda.manual_seed_all(random_seed) # if use multi-GPU
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    random.seed(random_seed)
    os.environ['PYTHONHASHSEED'] = str(random_seed)
    np.random.seed(random_seed)    
    # np.random.seed(random_seed)

class NeuralNet(nn.Module):
    def __init__(self):
        super(NeuralNet, self).__init__()
        self.fc1 = nn.Linear(56, 512)
        self.layer1 = self.make_layers(512, num_repeat=300)
        self.relu = nn.ReLU(inplace=True)
        self.fc5 = nn.Linear(512, 14)


    def forward(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        x = self.layer1(x)
        x = nn.Dropout(0.2)(x)
        x = self.fc5(x)
        return x

    def make_layers(self, value, num_repeat):
        layers = []
        for _ in range(num_repeat):
            layers.append(nn.Linear(value, value))
            layers.append(nn.ReLU(inplace=True))
        return nn.Sequential(*layers)

def numpy_to_tensor(variable):
    x = variable.values
    x = np.array(x, dtype=np.float32)
    x = torch.from_numpy(x)
    return x

def pandas_to_tensor(variable):
    return torch.tensor(variable.values)

def train_one_epoch(model, train_batch, criterion, optimizer, train_X, train_Y, device):
    model.train()
    train_loss = 0.0
    for i in range(train_batch):
        start = i * batch_size
        end = start + batch_size
        input = train_X[start:end].to(device, dtype=torch.float)
        label = train_Y[start:end].to(device, dtype=torch.float)

        input, label = input.to(device), label.to(device)
        outputs = model(input).squeeze()
        loss = criterion(outputs, label)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        train_loss += loss.item()
    print(f"train_loss : {train_loss}")
    
def val_one_epoch(model, val_batch, criterion, val_X, val_Y, device):
    model.eval()
    with torch.no_grad():
        val_loss = 0.0
        for i in range(val_batch):
            start = i * batch_size
            end = start + batch_size
            input = val_X[start:end].to(device, dtype=torch.float)
            label = val_Y[start:end].to(device, dtype=torch.float)

            input, label = input.to(device), label.to(device)
            outputs = model(input).squeeze()
            loss = criterion(outputs, label)
            val_loss += loss.item()
    print(f"val_loss : {val_loss}")
    
def datapreparation(train_df):
    # shuffle
    valset_ratio = 0.15
    train_df = train_df.sample(frac=1)

    train_df_X = train_df.filter(regex='X')
    train_df_Y = train_df.filter(regex='Y')

    valset_num = round(len(train_df_Y)*valset_ratio)

    val_df_X = pandas_to_tensor(train_df_X.iloc[:valset_num])
    val_df_Y = pandas_to_tensor(train_df_Y.iloc[:valset_num])    
    train_df_X = pandas_to_tensor(train_df_X.iloc[valset_num:])
    train_df_Y = pandas_to_tensor(train_df_Y.iloc[valset_num:])

    return train_df_X, train_df_Y, val_df_X, val_df_Y

def prediction(model, device, testPath) :
    preds = []

    model.eval()

    batch_size = 2048

    test_df = pd.read_csv(testPath).drop(columns=['ID'])
    test_df = test_df.sample(frac=1)
    test_df = test_df.filter(regex='X')
    test_df_X = pandas_to_tensor(test_df)

    test_batch = len(test_df_X) // batch_size
    for i in range(test_batch):
        start = i + batch_size
        end = start + batch_size

        input = test_df_X[start:end].to(device, dtype=torch.float)
        outputs = model(input).squeeze()
        preds.append(outputs.cpu().detach().numpy())
    preds = np.array(preds)
    preds = preds.reshape(preds.shape[0]*preds.shape[1], 14)
    
    # 마지막 batch에 남아있는 값들 계산
    last_input = test_df_X[test_batch*batch_size:].to(device, dtype=torch.float)
    last_outputs = model(last_input).squeeze()
    last_outputs = np.array(last_outputs.cpu().detach().numpy())

    preds = np.concatenate((preds, last_outputs), axis=0)  
    
    return preds

def submission(preds, submit) : 
    for idx, col in enumerate(submit.columns):
        if col=='ID':
            continue
        submit[col] = preds[:,idx-1]
    print('Done.')

    submit.to_csv(CFG.outPath+'submit_NN.csv', index=False)

if __name__ == '__main__':
    seedEverything(42)
    train_df = pd.read_csv(CFG.trainPath)    
    train_df_X, train_df_Y, val_df_X, val_df_Y = datapreparation(train_df)

    model = NeuralNet()
    model = model.to(CFG.device)
    optimizer = optim.Adam(model.parameters(),lr=3e-4)
    criterion = nn.L1Loss().cuda()

    num_epochs = 300
    batch_size = 2048
    
    train_batch = len(train_df_X) // batch_size
    val_batch = len(val_df_X) // batch_size
    
    for epoch in range(num_epochs):
        print(f"epoch:{epoch}")
        train_one_epoch(model, train_batch, criterion, optimizer, train_df_X, train_df_Y, CFG.device)
        val_one_epoch(model, val_batch, criterion, val_df_X, val_df_Y, CFG.device)
        # gc.collect()
        torch.save(model.state_dict(), CFG.weightsavePath+f'{epoch}_neuralnet.pt')
        print('\n')

    # TEST    
    model = NeuralNet()
    model = model.to(CFG.device)
    
    save_model = torch.load(CFG.weightsavePath + '299_neuralnet.pt', map_location=CFG.device)
    model.load_state_dict(save_model)
    
    preds = prediction(model, CFG.device, CFG.testPath)
    submit = pd.read_csv(CFG.submission)
    submission(preds, submit)

# epoch:299
# train_loss : 14.852047562599182
# val_loss : 1.8622652292251587
# leader board : 2.177217244
