#!/usr/bin/env python3
# modifier: phien.ngo
import os
import re
from argparse import ArgumentParser
import json
import glob
import sys

AGNI_KEYWORD_TEMP_FILES = 'agni_keywords.json'
TESTCASE_TEMPLATE_FILE = 'tcs.yaml'
CONFIG_FILE = 'config.json'
with open(CONFIG_FILE) as json_file:
  config_data = json.load(json_file)

def detectCommentLine(yaml_content, format_structure):
  regex = r"(#.*)\n([\s]{0,})(.*)\n"
  matches = re.finditer(regex, yaml_content, re.MULTILINE)
  for matchNum, match in enumerate(matches, start=1):
    if len(match.groups()) >= 2:
      comment_line = match.group(1)
      space_of_next_line = match.end(2) - match.start(2)
      next_line = match.group(3)
      if next_line + '@None' in format_structure:
        format_structure[comment_line.strip() + '@None'] = format_structure[next_line + '@None']
      else:
        format_structure[comment_line.strip() + '@None'] = space_of_next_line

  return format_structure

def detect_sub_block_by_words(yaml_content, format_structure, begin_from_list_words, end_word,
                              detect_character_per_line, space):
  found = False
  i = 0
  for line in yaml_content.split('\n'):
    i = i + 1
    if line.strip() in begin_from_list_words:
      found = True
      continue
    if end_word is not None:
      if found and end_word not in line:
        format_structure[line.strip() + '@' + str(i)] = space
      if end_word in line:
        found = False
        continue
    if detect_character_per_line is not None:
      if found and line.__contains__(detect_character_per_line):
        format_structure[line.strip() + '@' + str(i)] = space
      else:
        found = False
        continue

  return format_structure


def detect_file(yaml_content, format_structure):
  # detect testcase name
  testcase_name_list = re.findall('[\s]{0,}(.*)\n.*common_variables:', yaml_content)
  for item in testcase_name_list:
    format_structure[item.strip() + '@None'] = config_data['indent']['level_2']
  # detect all common variables
  format_structure = detect_sub_block_by_words(yaml_content, format_structure,
                                               ['common_variables:'], 'steps:', None, config_data['indent']['level_4'])
  # detect index step
  index_step_list = re.findall('\n[\s]{0,}(\d+:)\n', yaml_content)
  for item in index_step_list:
    format_structure[item.strip() + '@None'] = config_data['indent']['level_4']
  # detect stepname
  index_stepname_list = re.findall('\n[\s]{0,}\d+:[\s]{0,}(.*)\n', yaml_content)
  for item in index_stepname_list:
    format_structure[item.strip() + '@None'] = config_data['indent']['level_5']
  # detect comment line
  format_structure = detectCommentLine(yaml_content, format_structure)
  # detect sub command of run_event, run_keyword, create_dictionary_and_get,..
  format_structure = detect_sub_block_by_words(yaml_content, format_structure,
                                               ['run_event:', 'run_keyword:', 'create_dictionary_and_get:',
                                                'create_dictionary_and_check:'], 'unique_id', None, config_data['indent']['level_7'])
  # detect sub command of checks options
  format_structure = detect_sub_block_by_words(yaml_content, format_structure,
                                               ['checks:'], None, '- ', config_data['indent']['level_9'])
  # detect sub command of loop_over_list options
  format_structure = detect_sub_block_by_words(yaml_content, format_structure,
                                               ['loop_over_list:'], None, '- ', config_data['indent']['level_8'])

  return format_structure


def addBlankLine(yaml_content):
  contentToWrite = ''
  i=0
  found_comment = False
  for line in yaml_content.split('\n'):
    i=i+1
    if i==2:
      contentToWrite = contentToWrite + '\n' + line + '\n'
    else:
      comment_pattern = r'^\s{4}[\#]'
      if re.match(comment_pattern, line): # detect comment line
        contentToWrite = contentToWrite + '\n\n' + line + '\n'
        found_comment = True
        continue
      else:
        # detect testcase name
        step_pattern = r'^\s{4}[\w|\d]'
        if found_comment==False and re.match(step_pattern, line):
          contentToWrite = contentToWrite + '\n\n' + line + '\n'
        else:
          contentToWrite = contentToWrite + line + '\n'
          found_comment = False

  return  contentToWrite


def update_unique_ids_and_format(yaml_file=None, uid=1):
  directory, filename = os.path.split(yaml_file)
  format_structure = {
    "Granular_tests:@None": config_data['indent']['level_1'],
    "common_variables:@None": config_data['indent']['level_3'],
    "steps:@None": config_data['indent']['level_3'],
    "devices: device@None": config_data['indent']['level_7'],
    "checks:@None": config_data['indent']['level_7'],
    "loop_over_list:@None": config_data['indent']['level_7']
  }

  unique_ids_mapping = {}
  file_name_obj_arr = config_data['testcase_filename'].split('|')
  for item in  file_name_obj_arr:
    item_arr = item.split('@')
    unique_ids_mapping[item_arr[0]]= item_arr[1]

  yaml_file_name = os.path.split(yaml_file)[-1]

  if yaml_file_name in unique_ids_mapping.keys():
    uid = unique_ids_mapping[yaml_file_name]
  with open(yaml_file, 'r') as fr:
    yaml_content = fr.read()
  format_structure = detect_file(yaml_content, format_structure);
  counter = int(uid)
  steps_counter = 1
  fw = open('output/'+filename, 'w')
  i = 0
  contentToWrite = ''
  for line in yaml_content.split('\n'):
    i = i + 1
    if 'steps:' in line:
      steps_counter = 1
    if 'run_keyword:' in line or 'run_event:' in line \
            or 'create_dictionary_and_get' in line or 'create_dictionary_and_check' in line:
      format_structure[line.strip() + '@' + str(i)] = config_data['indent']['level_6']
    if 'unique_id:' in line:
      line = line.split(':')[0] + ': ' + str(counter)
      counter += 1
      format_structure[line.strip() + '@' + str(i)] = config_data['indent']['level_6']
    if re.search('^\s*\d+\:$', line):
      spaces = config_data['indent']['level_4']
      line = ' ' * spaces + str(steps_counter) + ':'
      steps_counter += 1

    # format indent for the line
    line_content = line.strip();
    if line_content + '@None' in format_structure.keys():
      line = ' ' * format_structure[line_content + '@None'] + line_content
    else:
      if line_content + '@' + str(i) in format_structure.keys():
        line = ' ' * format_structure[line_content + '@' + str(i)] + line_content

    if line.strip()!='':
      contentToWrite = contentToWrite + line + '\n'

  contentToWrite = addBlankLine(contentToWrite)
  fw.write(contentToWrite.strip())
  fw.close()


def generateStep(arrStepObjs, file_name, testcase_name, username):
  stepsToWrite = getHeaderContent(testcase_name, username)
  for stepObj in arrStepObjs:
    if stepObj != '':
      arrItem = stepObj.split('#')
      data = {'step_name': arrItem[0], 'keyword': arrItem[1]}
      if len(arrItem) >= 3:
        data['sub-keyword'] = arrItem[2]
      stepsToWrite = getStepContent(data, stepsToWrite)
  pth_of_file = 'output/test_case_generate.yaml'
  if file_name is not None:
    pth_of_file = 'output/' + file_name
  fw = open(pth_of_file, 'w')
  fw.write(stepsToWrite.strip())
  fw.close()
  update_unique_ids_and_format(pth_of_file)


def getHeaderContent(testcase_name, username):
  result = ''
  with open(TESTCASE_TEMPLATE_FILE, 'r') as fr:
    yaml_content = fr.read()

  write_code_before_step = True
  for line in yaml_content.split('\n'):
    if line.strip() == 'steps:':
      write_code_before_step = False
      result = result + line + '\n'
    if write_code_before_step == True:
      if testcase_name is not None:
        line = line.replace('testcase_name', testcase_name)
      if username is not None:
        line = line.replace('owner_name', username)
      result = result + line + '\n'
  return result


def getStepContent(stepObj, result):
  agni_keyword_data = {}
  with open(AGNI_KEYWORD_TEMP_FILES) as json_file:
    agni_keyword_data = json.load(json_file)['content']

  with open(TESTCASE_TEMPLATE_FILE, 'r') as fr:
    yaml_content = fr.read()

  found = False
  for line in yaml_content.split('\n'):
    # detect step to write
    if re.sub(r"#|@", "", line).strip() == stepObj['keyword']:
      found = True
      continue
    if found and '#####' not in line:
      line = line.replace('step_name', stepObj['step_name'])
      if 'sub-keyword' in stepObj.keys():
        if stepObj['sub-keyword'] in agni_keyword_data.keys():
          line = line.replace('<<sub-keyword>>', agni_keyword_data[stepObj['sub-keyword']])
        else:
          line = line.replace('<<sub-keyword>>', stepObj['sub-keyword'])
      result = result + line + '\n'
    if "#####" in line:
      found = False
      continue
  return result


def readAgniKeyword():
  agni_directory_path = config_data['agni_path'] + '\\'
  list_file_paths = glob.glob(agni_directory_path + "*.yaml")

  yaml_contents = ''
  for file_path in list_file_paths:
    with open(file_path, 'r') as fr:
      yaml_content = fr.read()
      yaml_contents = yaml_contents + '\n' + yaml_content

  list_keywords = re.findall('keyword:(.*)\n', yaml_contents)
  keywords_without_run_event = {}
  for keyword in list_keywords:

    if not keyword.strip().lower() == 'on config' and not keyword.strip().lower() == 'on cli':
      keyword_name = ''
      keyword = keyword.strip()
      keyword_content = re.sub(r"\'", "", keyword)
      keyword_splited_arr = re.split(r'\s{2,}', keyword_content)
      if len(keyword_splited_arr) == 1:
        keyword_name = keyword_splited_arr[0].strip().lower()
      else:
        str = re.sub(r"\$|\'|\"", "", keyword_content)
        for item in re.split(r'\s{2,}', str):
          if not '{' in item and not '=' in item:
            keyword_name = item.strip().lower()
            break
      if not keyword_name == '':
        if not keywords_without_run_event:
          if keyword_name not in keywords_without_run_event.keys():
            keywords_without_run_event[keyword_name] = keyword_content
        else:
          keywords_without_run_event[keyword_name] = keyword_content
  data = {
    'keywords': [],
    'content': keywords_without_run_event
  }
  if sys.version_info[0] < 3:
    data['keywords'] = keywords_without_run_event.keys()
  else:
    for i in keywords_without_run_event.keys():
      data['keywords'].append(i)

  with open(AGNI_KEYWORD_TEMP_FILES, 'w') as outfile:
    json.dump(data, outfile)


def main():
  argparser = ArgumentParser('python main.py -yaml=<yaml_file>')
  argparser.add_argument('-f', '--yaml_file', default=None, help='yaml file to update and format indent')
  argparser.add_argument('-u', '--unique_id', default=1, help='unique id to start for file')
  argparser.add_argument('-s', '--listStep', nargs='+', default=None,
                         help='String of Step in format step#keyword step1#keyword1')
  argparser.add_argument('-tn', '--testcase_name', default=None, help='Name of testcase')
  argparser.add_argument('-fn', '--file_name', default=None, help='File name of testcase')
  argparser.add_argument('-usr', '--username', default=None, help='User name')
  argparser.add_argument('-r', '--ragni', default=None, help='any value to read agni keyword from directory')
  args = argparser.parse_args()
  yaml_file = args.yaml_file
  start_unique_id = args.unique_id
  listStep = args.listStep
  testcase_name = args.testcase_name
  file_name = args.file_name
  username = args.username
  ragni = args.ragni
  if not os.path.isdir('output'):
    os.mkdir('output')
  if yaml_file is not None and start_unique_id is not None:
    update_unique_ids_and_format(yaml_file=yaml_file, uid=start_unique_id)
  if listStep is not None:
    generateStep(listStep, file_name, testcase_name, username)
  if ragni is not None:
    readAgniKeyword()


if __name__ == '__main__':
  main()
