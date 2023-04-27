#!/usr/bin/python3
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------------------------
# Запуск vnc сессий и создание vnc файлов в общей папке, для удалённого доступа
#------------------------------------------------------------------------------------------------

import os, sys, subprocess
from datetime import datetime
config = [] # Список параметров файла конфигурации

#------------------------------------------------------------------------------------------------
# Функция получения значений параметров конфигурации
def get_config(key):
  global config
  result = ''
  if not config:
    # Чтение файла конфигурации
    try:
      if os.path.isfile('/etc/vncgen/vncgen.conf'):
        configfile = open('/etc/vncgen/vncgen.conf')
      else:
        configfile = open('vncgen.conf')
    except IOError as error:
      log_write(error)
    else:
      for line in configfile:
        param = line.partition('=')[::2]
        if param[0].strip().isalpha() and param[0].strip().find('#') == -1:
          # Получение параметра
          config.append(param[0].strip())
          config.append(param[1].strip())
  try:
    result = config[config.index(key)+1]
  except ValueError as err:
    log_write('Config parameter '+str(key)+' not found, stoping server')
    exit(1)
  return result

#------------------------------------------------------------------------------------------------
# Функция записи в лог файл
def log_write(message):
  # Подготовка лог файла
  if not os.path.isfile(get_config('Log')):
    logdir = os.path.dirname(get_config('Log'))
    if not os.path.exists(logdir):
      os.makedirs(logdir)
    open(get_config('Log'),'a').close()
  else:
    # Проверка размера лог файла
    log_size = os.path.getsize(get_config('Log'))
    # Если лог файл больще 10М, делаем ротацию
    if log_size > 1024**2*10:
      try:
        os.remove(get_config('Log')+'.old')
      except:
        pass
      os.rename(get_config('Log'), get_config('Log')+'.old')
  # Запись в лог файл
  with open(get_config('Log'),'a') as logfile:
    logfile.write(str(datetime.now()).split('.')[0]+' '+message+'\n')

#------------------------------------------------------------------------------------------------
# Функция подготовки локальных профилей пользователей
def profile_prepare(username):
  # Есди нет профиля пользователя, то создаём его
  if not os.path.exists('/home/'+username):
    try:
      result = subprocess.check_output('adduser --disabled-password --gecos "" --quiet '+username+' 2>/dev/null', shell=True).decode().strip()
      log_write('Created user '+username)
      # Копирование настроек default в новый профиль пользователя
      try:
        result = subprocess.check_output('mkdir -p /home/'+username+'/.config/xfce4 && cp -rf /home/default/.config/xfce4 /home/'+username+'/.config && chown -R '+username+':'+username+' /home/'+username+'/.config/xfce4 2>/dev/null', shell=True).decode().strip()
        log_write('Copyed settings profile for user '+username)
      except subprocess.SubprocessError:
        log_write('Error on copying settings profile for user '+username)
      # Установка vnc пароля для пользователя
      try:
        result = subprocess.check_output('su - '+username+' -c "mkdir -p /home/'+username+'/.vnc && chown -R '+username+':'+username+' /home/'+username+'/.vnc && echo '+get_config('VNCClientPlainPassword')+' | vncpasswd -f > /home/'+username+'/.vnc/passwd && chmod 600 /home/'+username+'/.vnc/passwd"', shell=True).decode().strip()
        log_write('For user '+username+' setup vnc password '+get_config('VNCClientPlainPassword'))
      except subprocess.SubprocessError:
        log_write('Error setup password for user '+username)
    except subprocess.SubprocessError:
      log_write('Error on creating user '+username)

#------------------------------------------------------------------------------------------------
# Функция запуска vnc сессии и создания vnc файла
def run_session_and_make_file(username):
  # Если сессия для пользователя уже запущена, то не запускать
  try:
    user_session_port = subprocess.check_output('ps aux | grep -e "[d]esktop X -auth /home/'+username+'" | grep -oP "(?<=-rfbport )[^ ]*"', shell=True).decode().strip()
  except subprocess.SubprocessError:
    user_session_port = ''
  if not user_session_port:
    # Запуск vnc сессии для пользователя
    try:
      subprocess.check_output('su - '+username+' -c "vncserver -geometry '+get_config('VNCClientResolution')+'" 2>/dev/null', shell=True)
      user_session_port = subprocess.check_output('ps aux | grep -e "desktop X -auth /home/'+username+'" | grep -oP "(?<=rfbport )\w+"', shell=True).decode().strip()
      log_write('For user '+username+' running vnc session on port '+user_session_port)
    except subprocess.SubprocessError:
      log_write('Error running vnc session for user '+username)
    # Создание vnc файлов для подключения, в папке VNCShareRemote
    if os.path.exists(get_config('VNCShareRemote')):
      try:
        subprocess.check_output('echo [connection] > '+get_config('VNCShareRemote')+'/'+username+'.vnc', shell=True)
        subprocess.check_output('echo host='+os.uname().nodename+' >> '+get_config('VNCShareRemote')+'/'+username+'.vnc', shell=True)
        subprocess.check_output('echo port='+user_session_port+' >> '+get_config('VNCShareRemote')+'/'+username+'.vnc', shell=True)
        subprocess.check_output('echo password='+get_config('VNCClientEncryptPassword')+' >> '+get_config('VNCShareRemote')+'/'+username+'.vnc', shell=True)
        subprocess.check_output('echo [options] >> '+get_config('VNCShareRemote')+'/'+username+'.vnc', shell=True)
        subprocess.check_output('echo local_cursor_shape=0 >> '+get_config('VNCShareRemote')+'/'+username+'.vnc', shell=True)
        log_write('Created vnc file '+get_config('VNCShareRemote')+'/'+username+'.vnc')
      except subprocess.SubprocessError:
        log_write('Error write to vnc file '+get_config('VNCShareRemote')+'/'+username)
    else:
      log_write('Error path '+get_config('VNCShareRemote')+' not exist '+str(password))

#------------------------------------------------------------------------------------------------
# Функция работы с сессиями и пользователями
def run():
  #
  # Получение списка пользователей для группы ADGroup
  userslist = subprocess.check_output('ldapsearch -LLL -H ldap://'+get_config('ADServer')+'.'+get_config('DomainRealm')+' -D "'+get_config('ADUserName')+'@'+get_config('DomainRealm')+'" -w "'+get_config('ADUserPassword')+'" -b "dc='+get_config('DomainRealm').split('.')[0]+',dc='+get_config('DomainRealm').split('.')[1]+'" "(&(objectCategory=person)(memberOf=cn='+get_config('ADGroup')+',cn=Users,dc='+get_config('DomainRealm').split('.')[0]+',dc='+get_config('DomainRealm').split('.')[1]+'))" | grep sAMAccountName | cut -d" " -f2', shell=True).decode().strip()
  for user in userslist.split():
    profile_prepare(user)
    run_session_and_make_file(user)
  #

#------------------------------------------------------------------------------------------------
# Запуск программы
if __name__ =='__main__':
  run()
