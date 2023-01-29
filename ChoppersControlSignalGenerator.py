import os
import random
import subprocess
import sys
import math
from time import sleep

import PySimpleGUI as sg
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from basic_units import radians  # https://matplotlib.org/stable/gallery/units/radian_demo.html
import csv

from datetime import date


class Transistor:
    def __init__(self, purpose, name, time_turned_on_deg, time_is_on_deg):  # time in deg
        self.purpose = purpose
        self.name = name
        if time_is_on_deg < 0.0:
            self.time_turned_on_deg = 0.0
            self.time_is_on_deg = 0.0
            self.time_turned_off_deg = 0.0
        else:
            self.time_turned_on_deg = round(time_turned_on_deg % 360)
            self.time_is_on_deg = time_is_on_deg
            self.time_turned_off_deg = round((self.time_turned_on_deg + self.time_is_on_deg) % 360, 6)

    def isOn(self, currentTime):
        currentTime = round(currentTime % 360, 6)
        if self.time_is_on_deg == 0 or self.time_is_on_deg == 0.0:
            return 0
        elif self.time_turned_on_deg < self.time_turned_off_deg:
            if self.time_turned_on_deg <= currentTime < self.time_turned_off_deg:
                return 1
            else:
                return 0
        elif self.time_turned_on_deg > self.time_turned_off_deg:
            if self.time_turned_on_deg > currentTime >= self.time_turned_off_deg:
                return 0
            else:
                return 1
        else:
            return 1

    def updateParameter(self, new_time_is_on_deg, new_time_turned_on):
        if new_time_is_on_deg < 0.0:
            self.time_turned_on_deg = 0.0
            self.time_is_on_deg = 0.0
            self.time_turned_off_deg = 0.0
        else:
            if new_time_turned_on is not None:
                self.time_turned_on_deg = round(new_time_turned_on % 360, 6)
            self.time_is_on_deg = new_time_is_on_deg
            self.time_turned_off_deg = round((self.time_turned_on_deg + self.time_is_on_deg) % 360, 6)


def updateTimeIsOn(transistorList, new_time_is_on_deg, pauseTime):
    for idx in range(len(transistorList) - 1, -1, -2):
        transistorList[idx].updateParameter(new_time_is_on_deg, None)
        if int(new_time_is_on_deg) == 0:
            transistorList[idx - 1].updateParameter(360, 0)
        elif int(new_time_is_on_deg) == 360:
            transistorList[idx - 1].updateParameter(0, 0)
        else:
            transistorList[idx - 1].updateParameter(360 - new_time_is_on_deg - pauseTime * 2,
                                                transistorList[idx].time_turned_off_deg + pauseTime)


def getSignalAtTime(transistorsList, currentTime):  # currentTime in deg
    result = 0
    binumFormat = '0' + str(len(transistorsList)) + 'b'
    idx = len(transistorsList) - 1
    for ch in transistorsList:
        a = ch.isOn(currentTime)
        result += a * (2 ** idx)
        idx -= 1
    return format(result, binumFormat)


def deg2sec(deg, T) -> float:
    return deg * T / 360


def sec2deg(sec, T) -> float:
    if T != 0:
        return sec * 360 / T


def deg2rad(deg):
    return deg*math.pi/180


def ldeg2lrad(ldeg):
    result = []
    for angle in ldeg:
        result.append(deg2rad(angle))
    return result


# return list of time that signals change in degree and second and list of changed into signals
# T is needed because chopper and inverter have different Ts and T is needed when convert t to gamma
# def whenSignalChanges_sec_and_deg(transistorsList, numOfPeriod, T):
def whenSignalChanges_sec_and_deg(transistorsList, T, deltaGamma, numOfPeriods):
    result = ""
    repeat = 0
    t_deg = []
    t_usec = []
    signalMatrix = []
    t = [t_deg, t_usec, signalMatrix]
    gamma = 0.0
    # deltaGamma = 0.5
    # for gamma in range(0, numOfPeriod * 360, 1):
    while gamma < 360*numOfPeriods:
        # if gamma == repeat * 360 or gamma > repeat * 360:
        #    repeat += 1
        oldResult = result
        result = str(getSignalAtTime(transistorsList, gamma))
        if oldResult != result:
            t_deg.append(round(gamma, 4))
            t_usec.append(round(deg2sec(gamma, T) * 1000000, 6))
            signalMatrix.append(str(result))
        gamma += deltaGamma
    return t


# return list of time_length between adjacent t_points in degree and second
def getDelta_t_deg_and_usec(t, numOfPeriods, T=1e-3):
    t_deg = t[0]
    t_usec = t[1]
    dt_deg = []
    dt_usec = []
    dt = [dt_deg, dt_usec]
    if len(t[0]) == 1:
        return [360*numOfPeriods, T]
    for i in range(1, len(t_deg)):
        dt_deg.append(round(t_deg[i] - t_deg[i - 1], 6))
        dt_usec.append(round(t_usec[i] - t_usec[i - 1], 6))
        if i == len(t_deg) - 1:
            dt_deg.append(round(360*numOfPeriods - t_deg[i], 6))
            dt_usec.append(T*numOfPeriods * 1000000 - t_usec[i])
    return dt


def getDelta_t_deg(t_deg, numOfPeriods):
    dt_deg = []
    for i in range(1, len(t_deg)):
        dt_deg.append(round(t_deg[i] - t_deg[i - 1], 6))
        if i == len(t_deg) - 1:
            dt_deg.append(round(numOfPeriods*360 - t_deg[i], 6))
    return dt_deg


def getChopperList(numOfChoppers, time_diff_deg, time_is_on_deg,
                   pauseTime_deg):  # each chopper has 2 transistor H and L
    # smallPause = pauseTime * 360 / 1e-4
    # create chopper list depends on how many chopper pairs
    # Low transistor is turned on after 500 us after direct above high side transistor turned off and vise versa
    # if factor_a = 0% -> low side transistors are always on
    choppersList = []  # choppersList = [..., Bl_1, BH_1, AL_1, AH_1]
    idxA = 1
    idxB = 1
    if numOfChoppers % 2 == 0:
        for cpIdx1 in range(0, numOfChoppers):
            if cpIdx1 % 2 == 0:
                choppersList.insert(0, Transistor("chopper", "CP_AH_" + str(idxA),
                                                  (idxA - 1) * time_diff_deg,
                                                  time_is_on_deg))
                choppersList.insert(0, Transistor("chopper", "CP_AL_" + str(idxA),
                                                  (idxA - 1) * time_diff_deg + time_is_on_deg + pauseTime_deg if int(
                                                      time_is_on_deg) != 0
                                                  else (idxA - 1) * time_diff_deg,
                                                  360 - time_is_on_deg - pauseTime_deg * 2 if int(
                                                      time_is_on_deg) != 0 else 360))
                idxA += 1
            else:
                choppersList.insert(0, Transistor("chopper", "CP_BH_" + str(idxB),
                                                  (idxB - 1) * time_diff_deg + 180,
                                                  time_is_on_deg))
                choppersList.insert(0, Transistor("chopper", "CP_BL_" + str(idxB),
                                                  (
                                                          idxB - 1) * time_diff_deg + 180 + time_is_on_deg + pauseTime_deg if int(
                                                      time_is_on_deg) != 0
                                                  else (idxB - 1) * time_diff_deg + 180,
                                                  360 - time_is_on_deg - pauseTime_deg * 2 if int(
                                                      time_is_on_deg) != 0 else 360))
                idxB += 1
    else:
        for cpIdx2 in range(1, numOfChoppers * 2 + 1):
            choppersList.insert(0, Transistor("chopper", "CP_H_" + str(cpIdx2),
                                              (cpIdx2 - 1) * time_diff_deg,
                                              time_is_on_deg))
            choppersList.insert(0, Transistor("chopper", "CP_L_" + str(cpIdx2),
                                              (cpIdx2 - 1) * time_diff_deg + time_is_on_deg + pauseTime_deg if int(
                                                  time_is_on_deg) != 0
                                              else (cpIdx2 - 1) * time_diff_deg,
                                              360 - time_is_on_deg - pauseTime_deg * 2 if int(
                                                  time_is_on_deg) != 0 else 360))
    return choppersList


def createDict(transistorsList, t, dt):
    dict_t_msec = {"t (us)": t[1]}
    dict_dt_msec = {"dt (us)": dt[1]}
    dict_gamma = {"gamma (deg)": t[0]}
    dict_delta_gamma = {"d_gamma (deg)": dt[0]}
    signalMatrix_1 = t[2]
    # signalMatrix = []
    currentDict = {}
    signalList = []
    # for pot in t[0]:  # pot: point of time
    #   signalMatrix.append(str(createSignalAtTime(transistorsList, pot)))
    # print(signalMatrix1)
    # print(signalMatrix)
    for i in range(0, len(transistorsList)):
        for sig in signalMatrix_1:
            signalList.append(int(sig[i]))
        currentDict.update({transistorsList[i].name: signalList})
        signalList = []

    result = {**dict_gamma, **dict_delta_gamma, **currentDict}
    return result


def exportDictToExcel(dictList, numOfChoppers, factor, tableFileName):
    # https://xlsxwriter.readthedocs.io/example_pandas_table.html

    # cp_name = "CP-" + str(numOfChoppers) + "-" + str(factor) + "%"
    # inv_name = "INV-" + str(numOfInverters)

    # Create a Pandas dataframe
    # print(mydict[0])
    # print(mydict[1])
    # print(mydict[2])

    df_info = pd.DataFrame(dictList[0])
    df_cp = pd.DataFrame(dictList[1])

    sheetName = tableFileName.split(".")[0]

    # Create a Pandas Excel writer using XlsxWriter as the engine.
    writer = pd.ExcelWriter(tableFileName, engine='xlsxwriter')
    # Write the dataframe data to XlsxWriter. Turn off the default header and
    # index and skip one row to allow us to insert a user defined header.
    df_info.to_excel(writer, sheet_name=sheetName, startrow=1, header=True, index=False)
    df_cp.to_excel(writer, sheet_name=sheetName, startrow=df_info.shape[0] + 5, header=True, index=False)

    # Get the xlsxwriter workbook and worksheet objects.
    workbook = writer.book
    # worksheet_cp = writer.sheets[cp_name]
    # worksheet_inv = writer.sheets[inv_name]
    worksheet = writer.sheets[sheetName]
    worksheet.set_row(1, 50, None)
    worksheet.set_column(1, 60, None)

    # Get the dimensions of the dataframe.
    # (max_row_cp, max_col_cp) = df_cp.shape
    # (max_row_inv, max_col_inv) = df_inv.shape

    # Create a list of column headers, to use in add_table().
    # column_settings_cp = [{'header': column} for column in df_cp.columns]
    # column_settings_inv = [{'header': column} for column in df_inv.columns]

    # Add the Excel table structure. Pandas will add the data.
    # worksheet_cp.add_table(0, 0, max_row_cp, max_col_cp - 1, {'columns': column_settings_cp})
    # worksheet_inv.add_table(0, 0, max_row_inv, max_col_inv - 1, {'columns': column_settings_inv})

    # Make the columns wider for clarity.
    # worksheet_cp.set_column(0, max_col_cp - 1, 12)
    # worksheet_inv.set_column(0, max_col_inv - 1, 12)

    # Close the Pandas Excel writer and output the Excel file.
    writer.close()


def exportDictToText_Horizontal(mydict, textFileName, numOfPeriods, numOfChopper=None, factor_a=None, stepTime=None):
    fileName = str(textFileName)
    idx = 0
    with open(fileName, 'w') as f:
        if numOfChopper is not None and factor_a is not None and stepTime is not None:
            f.write(f"Number of choppers: {numOfChopper}\n"
                    f"Factor a: {factor_a} %\n"
                    f"Step time: {stepTime} grad\n\n")

        for key in mydict.keys():
            f.write("{:<20}".format(key))
        f.write("\n")
        while idx < len(mydict[key]):
            for value in mydict.values():
                f.write("{:<20}".format(value[idx]))
            f.write("\n")
            idx += 1
        f.write(f"\nNumber of signal switches: {int(len(mydict[key])/numOfPeriods)} in a period.")


def exportDictToText_Vertical(mydict, textFileName, numOfPeriods=1, numOfChopper=None, factor_a=None, stepTime=None):
    fileName = str(textFileName)
    list_time_deg = list(mydict.keys())
    list_time_rad = ldeg2lrad(list_time_deg)
    dt_list_rad = ldeg2lrad(getDelta_t_deg(list_time_deg, numOfPeriods) if len(list_time_deg) != 1 else [numOfPeriods*360])
    end_t_list_rad = list_time_rad[1:len(list_time_rad)] + [numOfPeriods*2*math.pi]

    numOfSwitches = int(len(list_time_deg) / numOfPeriods if len(list_time_deg) !=1 else 1)
    idx = 0
    with open(fileName, 'w') as f:
        if numOfChopper is not None and factor_a is not None:
            f.write(f"Number of choppers: {numOfChopper}\n"
                    f"Factor a: {factor_a} %\n"
                    f"Signal is read from right to left. (e.g...CP_BL_1, CP_BH_1, CP_AL_1, CP_AH_1)\n")
        f.write(f"\nNumber of signal switches: {numOfSwitches} in a period.\n")
        if stepTime is not None:
            f.write(f"Step time: {stepTime} grad\n")
        f.write("\n")
        f.write("{:<20}{:<20}{:<20}{:<20}\n".format("from", "duration", "to", "signal"))
        f.write(80 * "-" + "\n")
        for key in mydict:
            f.write("{:<20}{:<20}{:<20}{:<20}\n".format(round(deg2rad(key), 6),
                                                        round(dt_list_rad[idx], 6),
                                                        round(end_t_list_rad[idx], 6),
                                                        mydict[key]))
            idx += 1
            if idx % numOfSwitches == 0:
                f.write(80*"-"+"\n")


def getTimeTransistor_ONOFF(transistorList, numOfPeriod=1):
    result = {}
    for loop in range(numOfPeriod):
        for transistor in transistorList:
            time_turned_on = round(loop*360 + transistor.time_turned_on_deg, 6)
            time_turned_off = round(loop*360 + transistor.time_turned_off_deg, 6)
            result.update({time_turned_on:
                               str(getSignalAtTime(transistorList, time_turned_on))})
            result.update({time_turned_off:
                               str(getSignalAtTime(transistorList, time_turned_off))})
    result = dict(sorted(result.items()))
    return combineKeyIfTheValueSame(result)


def combineKeyIfTheValueSame(d):
    keys_values_list = [list(_) for _ in list(d.items())]
    temp = keys_values_list[0]
    idx = 1
    length = len(keys_values_list)
    while idx < length:
        if keys_values_list[idx][1] == temp[1]:
            keys_values_list.remove(keys_values_list[idx])
            idx -= 1
            length -= 1
        else:
            temp = keys_values_list[idx]
        idx += 1
    return dict(keys_values_list)


def visualCheck(transistorList, factor_a, numOfChoppers, numOfPeriods, fileName):
    visualCheck_items_list = [[] for _ in range(len(transistorList) + 1)]
    for tick in range(0, numOfPeriods*36000, 5):
        tick = tick / 100
        visualCheck_items_list[0].append(deg2rad(tick)*radians)
        signal = str(getSignalAtTime(transistorList, tick))
        signal_idx = 0
        while signal_idx < len(transistorList):
            visualCheck_items_list[signal_idx + 1].append(signal[signal_idx])
            signal_idx += 1

    fig, axs = plt.subplots(len(transistorList), sharey="all", sharex="all")

    if factor_a != 0:
        plt.gca().invert_yaxis()
    idx_subplot = 0
    for idx in range(len(visualCheck_items_list) - 1, 0, -1):
        if idx % 2 == 0:
            pltcolor = "r"
        else:
            pltcolor = "b"
        axs[idx_subplot].plot(visualCheck_items_list[0], visualCheck_items_list[idx], color=pltcolor,
                              label=transistorList[idx - 1].name, xunits=radians)
        axs[idx_subplot].legend(loc="center left")
        axs[idx_subplot].grid(visible=True, axis='both')
        idx_subplot += 1

    plt.xlabel('gamma')
    plt.suptitle(fileName, size=20)
    plt.show()


def main():
    global choppersList, numOfChoppers, old_numOfChoppers, factor_a, numOfInverters, T_cp_sec, deltaGamma, pauseTime, numOfPeriods
    T_cp_sec_default = 1e-3
    pauseTime_default = 500e-9
    deltaGamma_default = 0.144  # Equivalent to 2.5 MSPS for chopper (T=10e-3) and 25 MSPS for Inverter (T=10e-4)

    oldFileName = ''
    old_factor_a = 0
    old_numOfChoppers = 0

    # Create program's UI
    layout = [  # Standard layout
        [sg.Text("Number of choppers: ", key="IN", size=(25, 1)), sg.InputText(key='NUMofCP')],
        [sg.Text("Chopper on factor in % (0-100%): ", key="IN2", size=(25, 1)), sg.InputText(key='VALUEofa')],
        [sg.Text("Number of period: ", key="Input", size=(25, 1)),
         sg.InputText(default_text=1, key="NUMOFPERIOD")],
        # [sg.Checkbox("Default name, eg: 8CPs-25%-4INVs.xlsx", default=True, key='DEFNAME')],
        [sg.Text("Default name\neg: 2022-12-01_8CPs-25%")],
        [sg.Button("Custom name for table", key="CUSTOMNAME")],
        [sg.Text("Name for table: ", size=(25, 1), key='CUSTOMNAMETITLE'), sg.InputText(key='FILENAME', disabled=True)],
        [sg.Text("", size=(0, 1), key='ERR1', visible=False, text_color='#b30404')],
        [sg.Text("Note: \nSupport only .xlsx extension!" +
                 "\n" + str("Choppers' period = " + str(T_cp_sec_default) + " s as default."))],

        # Advanced options
        [sg.Button('Show advanced options', key='BUTTONSHOW', visible=True)],
        [sg.Text("Pause time between high and low transistor: ", key='PAUSETIMETXT', visible=False, size=(25, 2)),
         sg.InputText(key='PAUSETIME_VALUE', visible=False, default_text=pauseTime_default)],
        [sg.Text("Choppers' period in sec: ", size=(25, 1), key='CPTText', visible=False),
         sg.InputText(key='CPPeriod', visible=False, default_text=T_cp_sec_default)],
        [sg.Text("Delta gamma in degree: ", size=(25, 1), key='DELTAGAMMA', visible=False),
         sg.InputText(key='DELTAGAMMA_VAL', visible=False, default_text=deltaGamma_default)],
        [sg.Text("Note: 0.144° corresponds to 2.5 MSPS for chopper (T=1e-3)", key='NOTEDELTAGAMMA', visible=False)],
        [sg.Text("", size=(0, 1), key='ERR3', visible=False, text_color='#b30404')],
        [sg.Button('Hide advanced options', key='BUTTONHIDE', visible=False)],
        # End of advanced options

        [sg.Checkbox('Create and automatically open text file using simplified method', default=True,
                     key='OPENONOFFTIME')],
        [sg.Checkbox('Plot and automatically open plot', default=False, key='OPENPLOT')],
        [sg.Checkbox('Create and automatically open text file using sweep method (slow)', default=False,
                     key='OPENTEXT_SWEEP')],
        [sg.Checkbox('Create and automatically open tabel .xlsx file', default=False, key='OPENXLSX', visible=False)],

        [sg.Button("OK", key='OK1')],
        [sg.Text("Get signal at time [sec]: ", key="IN3", size=(25, 1), visible=False),
         sg.InputText(key='INPUT3', visible=False)],
        [sg.Text("Note: If any of above parameters is changed, create table again before getting signal",
                 visible=False, key='NOTE2')],
        [sg.Checkbox('Random time', key='CHOICE2', default=False, visible=False)],
        [sg.Button("Get signal", key='OK2', visible=False)],
        [sg.Text("", size=(0, 1), key='ERR2', visible=False, text_color='#b30404')],
        [sg.Text("", size=(0, 1), key='OUTPUT1', visible=False)],
        [sg.Text("", size=(0, 1), key='OUTPUT2', visible=False)]]

    # Program's displayed name
    window = sg.Window("Choppers Control Signal Generator", layout, finalize=True, resizable=True)

    # Key binding
    window.bind('<Return>', '-NEXT-')
    window.bind('<Down>', '-NEXT-')
    window.bind('<Up>', '-PREV-')

    # Lock for custom name
    customName_locked = 0

    # Program runs and reacts with pressed buttons (events)
    while 1:
        event, values = window.read()

        # Moving focus through input fields
        if event == '-NEXT-':
            next_element = window.find_element_with_focus().get_next_focus()
            next_element.set_focus()
        elif event == '-PREV-':
            prev_element = window.find_element_with_focus().get_previous_focus()
            prev_element.set_focus()

        # Advanced options
        elif event == 'BUTTONSHOW':
            window['BUTTONSHOW'].update(visible=False)
            window['PAUSETIMETXT'].update(visible=True)
            window['PAUSETIME_VALUE'].update(visible=True)
            window['BUTTONHIDE'].update(visible=True)
            window['CPTText'].update(visible=True)
            window['CPPeriod'].update(visible=True)
            window['DELTAGAMMA'].update(visible=True)
            window['DELTAGAMMA_VAL'].update(visible=True)
            window['NOTEDELTAGAMMA'].update(visible=True)
        elif event == 'BUTTONHIDE':
            window['BUTTONSHOW'].update(visible=True)
            window['PAUSETIMETXT'].update(visible=False)
            window['PAUSETIME_VALUE'].update(visible=False)
            window['BUTTONHIDE'].update(visible=False)
            window['CPTText'].update(visible=False)
            window['CPPeriod'].update(visible=False)
            window['DELTAGAMMA'].update(visible=False)
            window['DELTAGAMMA_VAL'].update(visible=False)
            window['NOTEDELTAGAMMA'].update(visible=False)
        # End of advanced options

        # Using different name and discard default name
        elif event == 'CUSTOMNAME' and customName_locked == 0:
            # window['CUSTOMNAMETITLE'].update(visible=True)
            window['FILENAME'].update(disabled=False)
            customName_locked = 1

        elif event == 'CUSTOMNAME' and customName_locked == 1:
            # window['CUSTOMNAMETITLE'].update(visible=False)
            window['FILENAME'].update(disabled=True)
            customName_locked = 0

        # Creating the tables
        elif event == 'OK1':
            # NumOfChoppers
            # numOfChoppers = int(input("Enter number of choppers: "))
            try:
                numOfChoppers = abs(int(values['NUMofCP']))
                window['NUMofCP'].update(value=numOfChoppers)
            except (AttributeError, ValueError, TypeError):
                window['ERR1'].update(value="Error: Invalid value of number of choppers!", visible=True)
                sleep(0.5)
                continue
            time_diff_deg = 360 / numOfChoppers

            # Factor_a
            # factor_a = float(input("Enter chopper on factor in %: "))
            try:
                factor_a = abs(float(values['VALUEofa']))
                #factor_a_list = [abs(float(_)) for _ in values['VALUEofa'].split(",")]
                if factor_a > 100:
                    factor_a = factor_a % 100
                    window['ERR1'].update(
                        value="Warning: chopper on factor will be changed to " + str(factor_a % 100) + "%.",
                        visible=True)
                    window['VALUEofa'].update(value=factor_a)
            except (AttributeError, ValueError, TypeError):
                window['ERR1'].update(value="Error: Invalid value of number of chopper factor a!", visible=True)
                sleep(0.5)
                continue
            cp_time_is_on_deg = round(factor_a / 100 * 360.0, 6)

            # Number of periods
            try:
                numOfPeriods = abs(int(values['NUMOFPERIOD']))
                if numOfPeriods < 1:
                    raise ValueError
            except (AttributeError, ValueError, TypeError):
                window['ERR1'].update(value="Error: Invalid value of number of periods!", visible=True)
                sleep(0.5)
                continue
            # ADVANCED OPTIONS
            # T_cp_sec
            try:
                T_cp_sec = abs(float(values['CPPeriod']))
            except (AttributeError, ValueError, TypeError, ValueError):
                window['ERR3'].update(value="Error: Invalid value of choppers' period", visible=True)
                sleep(0.5)
                continue
            # Pause time
            try:
                pauseTime_deg = sec2deg(float(values['PAUSETIME_VALUE']), T_cp_sec)
            except (AttributeError, ValueError, TypeError, ValueError):
                window['ERR3'].update(value="Error: Invalid value of pause time", visible=True)
                sleep(0.5)
                continue
            # Delta Gamma
            try:
                deltaGamma = abs(float(values['DELTAGAMMA_VAL']))
            except (AttributeError, ValueError, TypeError, ValueError):
                window['ERR3'].update(value="Error: Invalid value of delta gamma", visible=True)
                sleep(0.5)
                continue
            # ENDS OF ADVANCED OPTIONS

            # Remove error messages
            window['ERR1'].update(visible=False)
            window['ERR2'].update(visible=False)
            window['ERR3'].update(visible=False)

            # create new chopper list depends on number of choppers if choppers' number is changed
            if numOfChoppers != old_numOfChoppers:
                choppersList = getChopperList(numOfChoppers, time_diff_deg, cp_time_is_on_deg, pauseTime_deg)
                old_numOfChoppers = numOfChoppers
                old_factor_a = factor_a
            elif factor_a != old_factor_a:  # else update only the on time
                updateTimeIsOn(choppersList, cp_time_is_on_deg, pauseTime_deg)
                old_factor_a = factor_a

            # Temporary, there are bugs in updateTimeIsOn / bug is fixed
            # choppersList = getChopperList(numOfChoppers, time_diff_deg, cp_time_is_on_deg, pauseTime_deg)
            # create dict time on/off (key) and transistor name (value)
            time_dict_sorted = getTimeTransistor_ONOFF(choppersList, numOfPeriods)
            # print(time_dict_sorted)

            # Dictionary for basic information in exported xlxs file

            # remove blank space in fileName and make it valid
            fileName = values['FILENAME'].replace(" ", "")
            if fileName == '' or fileName.split("_")[1] == oldFileName:
                # Add date to fileName
                fileName = str(date.today()) + "_" + str(numOfChoppers) + "CPs-" + str(factor_a) + "%-" + str(numOfPeriods) +"Ts"
                window['FILENAME'].update(value=fileName)

            oldFileName = fileName.split("_")[1]
            fileName_xlsx = fileName + ".xlsx"
            fileName_text_slow = fileName + "_SWEEP" + ".txt"
            fileName_text = fileName + ".txt"
            # fileName_time_table = "TimeTable-" + str(factor_a) + "%.txt"
            # print(fileName)

            # Create and automatically open xlsx file
            if values['OPENXLSX'] or values['OPENTEXT_SWEEP']:
                info_dict = {
                    'Number\nof\nchoppers': [numOfChoppers],
                    'Choppers\non\nfactor\n[%]': [factor_a],
                    "Choppers'\nperiod\n[sec]": [T_cp_sec]
                }
                # Get time that controlling signal for choppers changes
                cp_t_changes = whenSignalChanges_sec_and_deg(choppersList, T_cp_sec, deltaGamma, numOfPeriods)
                # Get time between changes
                if int(factor_a) % 100 == 0:
                    cp_dt_btw_changes = [[360.0], [T_cp_sec]]  # Special case, a=0% other a=100%
                else:
                    cp_dt_btw_changes = getDelta_t_deg_and_usec(cp_t_changes, numOfPeriods, T_cp_sec)
                # Dict for exported file
                cp_dict = createDict(choppersList, cp_t_changes, cp_dt_btw_changes)

                dictList = [info_dict, cp_dict]
                # print(fileName_xlsx)
                if values['OPENXLSX']:  # Disabled because Dr. Spichartz does not want this
                    exportDictToExcel(dictList, numOfChoppers, factor_a, fileName_xlsx)
                    if sys.platform == "darwin":
                        opener = "open"
                        subprocess.call([opener, fileName_xlsx])
                    else:
                        os.startfile(fileName_xlsx)
                # Create and automatically open txt file
                if values['OPENTEXT_SWEEP']:
                    exportDictToText_Horizontal(cp_dict, fileName_text_slow, numOfPeriods, numOfChoppers, factor_a, deltaGamma)
                    if sys.platform == "darwin":
                        opener = "open"
                        subprocess.call([opener, fileName_text_slow])
                    else:
                        os.startfile(fileName_text_slow)

            # Create and automatically open timetable text
            if values['OPENONOFFTIME']:
                exportDictToText_Vertical(time_dict_sorted, fileName_text, numOfPeriods, numOfChoppers, factor_a)
                if sys.platform == "darwin":
                    opener = "open"
                    subprocess.call([opener, fileName_text])
                else:
                    os.startfile(fileName_text)

            # Visual Check
            if values['OPENPLOT']:
                visualCheck(choppersList, factor_a, numOfChoppers, numOfPeriods, fileName)


        #Features for debug and playing purposes

            # window['IN3'].update(visible=True)
            # window['NOTE2'].update(visible=True)
            # window['INPUT3'].update(visible=True)
            # window['OK2'].update(visible=True)
            # window['CHOICE2'].update(visible=True)

        # Get signal at random times
        elif event == 'OK2':
            if not values['CHOICE2']:
                try:
                    timeInSec = float(values['INPUT3'])
                except (AttributeError, ValueError, TypeError, ValueError):
                    window['ERR2'].update(value="Error: Invalid value of time!", visible=True)
                    sleep(0.5)
                    continue
            else:
                timeInSec = random.uniform(1e-3, 1e2) * 10 ** (-3)
                window['INPUT3'].update(value=timeInSec)

            cp_timeInDeg = sec2deg(timeInSec, T_cp_sec) % 360
            choppersSignal = getSignalAtTime(choppersList, cp_timeInDeg)

            window['OUTPUT1'].update(value="Signal for choppers: " + str(choppersSignal), visible=True)

        elif event == sg.WINDOW_CLOSED:
            break

        # if input("Restart? [y]es or [n]o: ") == 'y':
        # continue
        # else:
        # break
        # choice = input("Choose 1 for checking when changes happen \n"
        #               "Choose 2 for checking which IGBT are on at chosen time in second \n"
        #               "Choose 3 to export data table to excel\n")
        # choice = 3
        # if choice == '1':
        #    whenSignalsChanges_printOut(choppersList, numOfPeriod, T_cp_sec)
        #    print(time_diff_deg)
        #    print(cp_time_is_on_deg)
        # elif choice == '2':
        #    while 1:
        #        try:
        #            timeinSec = float(input("At (sec): "))
        #        except:
        #            break
        #        getSignalAtTime_manual(choppersList, numOfPeriod, T_cp_sec, timeinSec)


if __name__ == '__main__':
    main()
