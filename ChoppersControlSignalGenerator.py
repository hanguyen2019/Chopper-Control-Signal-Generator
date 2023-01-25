import os
import random
import subprocess
import sys
from time import sleep

import PySimpleGUI as sg
import pandas as pd
import matplotlib.pyplot as plt
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
            self.time_turned_on_deg = time_turned_on_deg % 360
            self.time_is_on_deg = time_is_on_deg
            self.time_turned_off_deg = (self.time_turned_on_deg + self.time_is_on_deg) % 360

    def isOn(self, currentTime):
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
            self.time_is_on_deg = new_time_is_on_deg
            if new_time_turned_on is not None:
                self.time_turned_on_deg = new_time_turned_on % 360
            self.time_turned_off_deg = (self.time_turned_on_deg + self.time_is_on_deg) % 360


def updateTimeIsOn(transistorList, new_time_is_on_deg, pauseTime):
    for idx in range(len(transistorList) - 1, -1, -2):
        transistorList[idx].updateParameter(new_time_is_on_deg, None)
        transistorList[idx - 1].updateParameter(360 - new_time_is_on_deg - pauseTime * 2,
                                                transistorList[idx].time_turned_off_deg + pauseTime)


def createSignalAtTime(transistorsList, currentTime):  # currentTime in deg
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


# return list of time that signals change in degree and second and list of changed into signals
# T is needed because chopper and inverter have different Ts and T is needed when convert t to gamma
# def whenSignalChanges_sec_and_deg(transistorsList, numOfPeriod, T):
def whenSignalChanges_sec_and_deg(transistorsList, T, deltaGamma):
    result = ""
    repeat = 0
    t_deg = []
    t_usec = []
    signalMatrix = []
    t = [t_deg, t_usec, signalMatrix]
    gamma = 0.0
    # deltaGamma = 0.5
    # for gamma in range(0, numOfPeriod * 360, 1):
    while gamma < 360:
        # if gamma == repeat * 360 or gamma > repeat * 360:
        #    repeat += 1
        oldResult = result
        result = str(createSignalAtTime(transistorsList, gamma))
        if oldResult != result:
            t_deg.append(round(gamma, 4))
            t_usec.append(round(deg2sec(gamma, T) * 1000000, 6))
            signalMatrix.append(str(result))
        gamma += deltaGamma
    return t


# return list of time_length between adjacent t_points in degree and second
def getDelta_t_deg_and_usec(t, T=1e-3):
    t_deg = t[0]
    t_usec = t[1]
    dt_deg = []
    dt_usec = []
    dt = [dt_deg, dt_usec]
    for i in range(1, len(t_deg)):
        dt_deg.append(round(t_deg[i] - t_deg[i - 1], 4))
        dt_usec.append(round(t_usec[i] - t_usec[i - 1], 6))
        if i == len(t_deg) - 1:
            dt_deg.append(round(360 - t_deg[i], 4))
            dt_usec.append(T * 1000000 - t_usec[i])
    return dt


def getDelta_t_deg(t_deg):
    dt_deg = []
    for i in range(1, len(t_deg)):
        dt_deg.append(round(t_deg[i] - t_deg[i - 1], 4))
        if i == len(t_deg) - 1:
            dt_deg.append(round(360 - t_deg[i], 4))
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


def exportDictToText_Horizontal(mydict, textFileName, numOfChopper=None, factor_a=None, stepTime=None):
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


def exportDictToText_Vertical(mydict, textFileName, numOfChopper=None, factor_a=None, stepTime=None):
    fileName = str(textFileName)
    list_time_deg = list(mydict.keys())
    dt_list_deg = getDelta_t_deg(list_time_deg)
    idx = 0
    with open(fileName, 'w') as f:
        if numOfChopper is not None and factor_a is not None:
            f.write(f"Number of choppers: {numOfChopper}\n"
                    f"Factor a: {factor_a} %\n")
        if stepTime is not None:
            f.write(f"Step time: {stepTime} grad\n")
        f.write("\n")
        for key in mydict:
            f.write("{:<20}{:<20}{:<20}\n".format(round(key, 6), dt_list_deg[idx], mydict[key]))
            idx += 1


def getTimeONOFF(transistorList):
    result = {}
    result_special_case = {}  # 0% and 100%
    for transistor in transistorList:
        result.update({transistor.time_turned_on_deg:
                           str(createSignalAtTime(transistorList, transistor.time_turned_on_deg))})
        result.update({transistor.time_turned_off_deg:
                           str(createSignalAtTime(transistorList, transistor.time_turned_off_deg))})
    # TODO: special cases a 0% and 100%
    return result


def combineKeyIfTheValueSame(d, k1, k2):
    if d[k1] == d[k2]:
        return {k1+k2: d[k1]}


def visualCheck(transistorList, factor_a, numOfChoppers):
    visualCheck_items_list = [[] for _ in range(len(transistorList) + 1)]
    for tick in range(0, 36000, 1):
        tick = tick / 100
        visualCheck_items_list[0].append(tick)
        signal = str(createSignalAtTime(transistorList, tick))
        signal_idx = 0
        while signal_idx < len(transistorList):
            visualCheck_items_list[signal_idx + 1].append(signal[signal_idx])
            signal_idx += 1

    fig, axs = plt.subplots(int(len(transistorList) / 2), sharex=True, sharey=True)
    idx_subplot = 0
    for idx in range(len(visualCheck_items_list) - 1, 0, -2):
        axs[idx_subplot].plot(visualCheck_items_list[0], visualCheck_items_list[idx - 1],
                              label=transistorList[idx - 1 - 1].name)
        axs[idx_subplot].plot(visualCheck_items_list[0], visualCheck_items_list[idx],
                              label=transistorList[idx - 1].name)
        axs[idx_subplot].legend(loc="center left")
        idx_subplot += 1
    plt.xticks(list(range(0, 361, 10)))
    plt.xlabel('gamma')
    # plt.gca().invert_yaxis()
    plt.suptitle(str(date.today()) + "_" + str(numOfChoppers) + "CP_" + str(factor_a) + "%")
    plt.show()


def main():
    global choppersList, numOfChoppers, old_numOfChoppers, factor_a, numOfInverters, T_cp_sec, deltaGamma, pauseTime
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
        # [sg.Text("Number of period: "      , key="Input", size=(25, 1)), sg.InputText()],
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
         sg.InputText(key='PAUSETIME_VALUE', visible=False)],
        [sg.Text("Choppers' period in sec: ", size=(25, 1), key='CPTText', visible=False),
         sg.InputText(key='CPPeriod', visible=False)],
        [sg.Text("Delta gamma in degree: ", size=(25, 1), key='DELTAGAMMA', visible=False),
         sg.InputText(key='DELTAGAMMA_VAL', visible=False)],
        [sg.Text("Note: 0.144° corresponds to 2.5 MSPS for chopper (T=1e-3)", key='NOTEDELTAGAMMA', visible=False)],
        [sg.Text("", size=(0, 1), key='ERR3', visible=False, text_color='#b30404')],
        [sg.Button('Hide advanced options', key='BUTTONHIDE', visible=False)],
        # End of advanced options

        [sg.Checkbox('Create and automatically open text file using simplified method', default=True, key='OPENONOFFTIME')],
        [sg.Checkbox('Create and automatically open text file using sweep method (slow)', default=False,
                     key='OPENTEXT')],
        [sg.Checkbox('Create and automatically open tabel .xlsx file', default=False, key='OPENXLSX')],
        [sg.Checkbox('Plot and automatically open plot', default=False, key='OPENPLOT')],
        [sg.Button("Create table", key='OK1')],
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
    window = sg.Window("Choppers Control Signal Generator", layout, finalize=True)

    # Key binding
    window.bind('<Return>', '-NEXT-')
    window.bind('<Down>', '-NEXT-')
    window.bind('<Up>', '-PREV-')

    # Lock for custom name
    customName_locked = 0

    # Program runs and reacts with pressed buttons (events)
    while 1:
        event, values = window.read()
        # ADVANCED OPTIONS
        # Pause time
        try:  # Used to remove annoying error in python
            if values['PAUSETIME_VALUE'] == '':
                pauseTime = pauseTime_default
                window['PAUSETIME_VALUE'].update(value=pauseTime)
            else:
                try:
                    T_cp_sec = abs(float(values['PAUSETIME_VALUE']))
                except (AttributeError, ValueError, TypeError, ValueError):
                    window['ERR3'].update(value="Error: Invalid value of pause time", visible=True)
                    sleep(0.5)
                    continue
        except TypeError:
            pass
        # T_cp_sec
        try:  # Used to remove annoying error in python
            if values['CPPeriod'] == '':
                T_cp_sec = T_cp_sec_default
                window['CPPeriod'].update(value=T_cp_sec)
            else:
                try:
                    T_cp_sec = abs(float(values['CPPeriod']))
                except (AttributeError, ValueError, TypeError, ValueError):
                    window['ERR3'].update(value="Error: Invalid value of choppers' period", visible=True)
                    sleep(0.5)
                    continue
        except TypeError:
            pass
        # Delta Gamma
        try:  # Used to remove annoying error in python
            if values['DELTAGAMMA_VAL'] == '':
                deltaGamma = deltaGamma_default
                window['DELTAGAMMA_VAL'].update(value=deltaGamma)
            else:
                try:
                    deltaGamma = abs(float(values['DELTAGAMMA_VAL']))
                except (AttributeError, ValueError, TypeError, ValueError):
                    window['ERR3'].update(value="Error: Invalid value of delta gamma", visible=True)
                    sleep(0.5)
                    continue
        except TypeError:
            pass
        # ENDS OF ADVANCED OPTIONS

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
            except (AttributeError, ValueError, TypeError, ValueError):
                window['ERR1'].update(value="Error: Invalid value of number of choppers!", visible=True)
                sleep(0.5)
                continue
            time_diff_deg = 360 / numOfChoppers

            # Factor_a
            # factor_a = float(input("Enter chopper on factor in %: "))
            try:
                factor_a = abs(float(values['VALUEofa']))
                # factor_a_list = values['VALUEofa'].split(",")
                if factor_a > 100:
                    factor_a = factor_a % 100
                    window['ERR1'].update(
                        value="Warning: chopper on factor will be changed to " + str(factor_a % 100) + "%.",
                        visible=True)
                    window['VALUEofa'].update(value=factor_a)
            except (AttributeError, ValueError, TypeError, ValueError):
                window['ERR1'].update(value="Error: Invalid value of number of chopper factor a!", visible=True)
                sleep(0.5)
                continue
            cp_time_is_on_deg = factor_a / 100 * 360.0

            pauseTime_deg = sec2deg(pauseTime, T_cp_sec)

            # create new chopper list depends on number of choppers if choppers' number is changed
            if numOfChoppers != old_numOfChoppers:
                choppersList = getChopperList(numOfChoppers, time_diff_deg, cp_time_is_on_deg, pauseTime_deg)
                old_numOfChoppers = numOfChoppers
                old_factor_a = factor_a
            elif factor_a != old_factor_a:  # else update only the on time
                updateTimeIsOn(choppersList, cp_time_is_on_deg, pauseTime_deg)
                old_factor_a = factor_a

            # create dict time on/off (key) and transistor name (value)
            time_dict_sorted = dict(sorted(getTimeONOFF(choppersList).items()))
            # print(time_dict_sorted)

            # Dictionary for basic information in exported xlxs file
            info_dict = {
                'Number\nof\nchoppers': [numOfChoppers],
                'Choppers\non\nfactor\n[%]': [factor_a],
                "Choppers'\nperiod\n[sec]": [T_cp_sec]
            }

            # Get time that controlling signal for choppers changes
            cp_t_changes = whenSignalChanges_sec_and_deg(choppersList, T_cp_sec, deltaGamma)
            # Get time between changes
            if int(factor_a) % 100 == 0:
                cp_dt_btw_changes = [[360.0], [T_cp_sec]]  # Special case, a=0% other a=100%
            else:
                cp_dt_btw_changes = getDelta_t_deg_and_usec(cp_t_changes, T_cp_sec)
            # Dict for exported file
            cp_dict = createDict(choppersList, cp_t_changes, cp_dt_btw_changes)
            # print(cp_dict)

            # print(inv_dict)
            dictList = [info_dict, cp_dict]

            # remove blank space in fileName and make it valid
            fileName = values['FILENAME'].replace(" ", "")
            if fileName == '' or fileName.split("_")[1] == oldFileName:
                # Add date to fileName
                fileName = str(date.today()) + "_" + str(numOfChoppers) + "CPs-" + str(int(factor_a)) + "%"
                window['FILENAME'].update(value=fileName)

            oldFileName = fileName.split("_")[1]
            fileName_xlsx = fileName + ".xlsx"
            fileName_text_slow = fileName + "_SWEEP" + ".txt"
            fileName_text = fileName + ".txt"
            #fileName_time_table = "TimeTable-" + str(factor_a) + "%.txt"
            # print(fileName)

            # Create and automatically open xlsx file
            if values['OPENXLSX']:
                print(fileName_xlsx)
                exportDictToExcel(dictList, numOfChoppers, factor_a, fileName_xlsx)
                if sys.platform == "darwin":
                    opener = "open"
                    subprocess.call([opener, fileName_xlsx])
                else:
                    os.startfile(fileName_xlsx)
            # Create and automatically open txt file
            if values['OPENTEXT']:
                exportDictToText_Horizontal(cp_dict, fileName_text_slow, numOfChoppers, factor_a, deltaGamma)
                if sys.platform == "darwin":
                    opener = "open"
                    subprocess.call([opener, fileName_text_slow])
                else:
                    os.startfile(fileName_text_slow)

            # Create and automatically open timetable text
            if values['OPENONOFFTIME']:
                exportDictToText_Vertical(time_dict_sorted, fileName_text, numOfChoppers, factor_a)
                if sys.platform == "darwin":
                    opener = "open"
                    subprocess.call([opener, fileName_text])
                else:
                    os.startfile(fileName_text)

            # Visual Check
            if values['OPENPLOT']:
                visualCheck(choppersList, factor_a, numOfChoppers)

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
            choppersSignal = createSignalAtTime(choppersList, cp_timeInDeg)

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
