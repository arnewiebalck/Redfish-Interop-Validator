
# Copyright Notice:
# Copyright 2016-2020 DMTF. All rights reserved.
# License: BSD 3-Clause License. For full text see link: https://github.com/DMTF/Redfish-Interop-Validator/blob/master/LICENSE.md


if __name__ != '__main__':
    import traverseService as rst
    from commonRedfish import getNamespace, getType
else:
    import argparse
    from bs4 import BeautifulSoup
    import os, csv
import RedfishLogo as logo
from types import SimpleNamespace
from collections import Counter, OrderedDict
import html
import json


def wrapTag(string, tag='div', attr=None):
    string = str(string)
    ltag, rtag = '<{}>'.format(tag), '</{}>'.format(tag)
    if attr is not None:
        ltag = '<{} {}>'.format(tag, attr)
    return ltag + string + rtag

# hack in tagnames into module namespace
for tagName in ['tr', 'td', 'th', 'div', 'b', 'table', 'body', 'head']:
    globals()[tagName] = lambda string, attr=None, tag=tagName: wrapTag(string, tag=tag, attr=attr)


def infoBlock(strings, split='<br/>', ffunc=None, sort=True):
    if isinstance(strings, dict):
        infos = [b('{}: '.format(y)) + str(x) for y,x in (sorted(strings.items()) if sort else strings.items())]
    else:
        infos = strings
    return split.join([ffunc(*x) for x in enumerate(infos)] if ffunc is not None else infos)


def tableBlock(lines, titles, widths=None, ffunc=None):
    widths = widths if widths is not None else [100 for x in range(len(titles))]
    attrlist = ['style="width:{}%"'.format(str(x)) for x in widths]
    tableHeader = tr(''.join([th(x,y) for x,y in zip(titles,attrlist)]))
    for line in lines:
        tableHeader += tr(''.join([ffunc(cnt, x) if ffunc is not None else td(x) for cnt, x in enumerate(line)]))
    return table(tableHeader)


def applySuccessColor(num, entry):
    if num < 4:
        return wrapTag(entry, 'td')
    success_col = str(entry)
    if 'FAIL' in str(success_col).upper():
        entry = '<td class="fail center">' + str(success_col) + '</td>'
    elif 'DEPRECATED' in str(success_col).upper():
        entry = '<td class="warn center">' + str(success_col) + '</td>'
    elif 'PASS' in str(success_col).upper():
        entry = '<td class="pass center">' + str(success_col) + '</td>'
    else:
        entry = '<td class="center">' + str(success_col) + '</td>'
    return entry


def applyInfoSuccessColor(num, entry):
    if 'fail' in entry or 'exception' in entry:
        style = 'class="fail"'
    elif 'warn' in entry:
        style = 'class="warn"'
    else:
        style = None
    return div(entry, attr=style)


def renderHtml(results, finalCounts, tool_version, startTick, nowTick, printCSV):
    # Render html
    config = rst.config
    config_str = ', '.join(sorted(list(config.keys() - set(['systeminfo', 'targetip', 'password', 'description']))))
    rsvLogger = rst.getLogger()
    sysDescription, ConfigURI = (config['systeminfo'], config['targetip'])
    logpath = config['logpath']

    # wrap html
    htmlPage = ''
    htmlStrTop = '<head><title>Conformance Test Summary</title>\
            <style>\
            .pass {background-color:#99EE99}\
            .fail {background-color:#EE9999}\
            .warn {background-color:#EEEE99}\
            .bluebg {background-color:#BDD6EE}\
            .button {padding: 12px; display: inline-block}\
            .center {text-align:center;}\
            .log {text-align:left; white-space:pre-wrap; word-wrap:break-word; font-size:smaller}\
            .title {background-color:#DDDDDD; border: 1pt solid; font-height: 30px; padding: 8px}\
            .titlesub {padding: 8px}\
            .titlerow {border: 2pt solid}\
            .results {transition: visibility 0s, opacity 0.5s linear; display: none; opacity: 0}\
            .resultsShow {display: block; opacity: 1}\
            body {background-color:lightgrey; border: 1pt solid; text-align:center; margin-left:auto; margin-right:auto}\
            th {text-align:center; background-color:beige; border: 1pt solid}\
            td {text-align:left; background-color:white; border: 1pt solid; word-wrap:break-word;}\
            table {width:90%; margin: 0px auto; table-layout:fixed;}\
            .titletable {width:100%}\
            </style>\
            </head>'
    htmlStrBodyHeader = ''
    # Logo and logname
    infos = [wrapTag('##### Redfish Conformance Test Report #####', 'h2')]
    infos.append(wrapTag('<img align="center" alt="DMTF Redfish Logo" height="203" width="288"'
                         'src="data:image/gif;base64,' + logo.logo + '">', 'h4'))
    infos.append('<h4><a href="https://github.com/DMTF/Redfish-Interop-Validator">'
                 'https://github.com/DMTF/Redfish-Interop-Validator</a></h4>')
    infos.append('Tool Version: {}'.format(tool_version))
    infos.append(startTick.strftime('%c'))
    infos.append('(Run time: {})'.format(
        str(nowTick-startTick).rsplit('.', 1)[0]))
    infos.append('<h4>This tool is provided and maintained by the DMTF. '
                 'For feedback, please open issues<br>in the tool\'s Github repository: '
                 '<a href="https://github.com/DMTF/Redfish-Interop-Validator/issues">'
                 'https://github.com/DMTF/Redfish-Interop-Validator/issues</a></h4>')

    htmlStrBodyHeader += tr(th(infoBlock(infos)))

    infos = {'System': ConfigURI, 'Description': sysDescription}
    htmlStrBodyHeader += tr(th(infoBlock(infos)))

    infos = {'Profile': config['profile'], 'Schema': config['schema']}
    htmlStrBodyHeader += tr(th(infoBlock(infos)))

    infos = {x: config[x] for x in config if x not in ['systeminfo', 'targetip', 'password', 'description', 'profile', 'schema']}
    block = tr(th(infoBlock(infos, '|||')))
    for num, block in enumerate(block.split('|||'), 1):
        sep = '<br/>' if num % 4 == 0 else ',&ensp;'
        sep = '' if num == len(infos) else sep
        htmlStrBodyHeader += block + sep

    htmlStrTotal = '<div>Final counts: '
    for countType in sorted(finalCounts.keys()):
        if finalCounts.get(countType) == 0:
            continue
        htmlStrTotal += '{p}: {q},   '.format(p=countType, q=finalCounts.get(countType, 0))
    htmlStrTotal += '</div><div class="button warn" onClick="arr = document.getElementsByClassName(\'results\'); for (var i = 0; i < arr.length; i++){arr[i].className = \'results resultsShow\'};">Expand All</div>'
    htmlStrTotal += '</div><div class="button fail" onClick="arr = document.getElementsByClassName(\'results\'); for (var i = 0; i < arr.length; i++){arr[i].className = \'results\'};">Collapse All</div>'

    htmlStrBodyHeader += tr(td(htmlStrTotal))

    htmlPage = rst.currentService.metadata.to_html()
    for cnt, item in enumerate(results):
        entry = []
        val = results[item]
        rtime = '(response time: {})'.format(val['rtime'])

        if len(val['messages']) == 0 and len(val['errors']) == 0:
            continue

        # uri block
        prop_type = val['fulltype']
        if prop_type is not None:
            namespace = getNamespace(prop_type)
            type_name = getType(prop_type)

        infos_a = [str(val.get(x)) for x in ['uri', 'samplemapped'] if val.get(x) not in ['',None]]
        infos_a.append(rtime)
        infos_a.append(type_name)
        uriTag = tr(th(infoBlock(infos_a, '&ensp;'), 'class="titlerow bluebg"'))
        entry.append(uriTag)

        # info block
        infos_b = [str(val.get(x)) for x in ['uri'] if val.get(x) not in ['',None]]
        infos_b.append(rtime)
        infos_b.append(div('Show Results', attr='class="button warn" onClick="document.getElementById(\'resNum{}\').classList.toggle(\'resultsShow\');"'.format(cnt)))
        buttonTag = td(infoBlock(infos_b), 'class="title" style="width:30%"')

        infos_content = [str(val.get(x)) for x in ['context', 'origin', 'fulltype']]
        infos_c = {y: x for x,y in zip(infos_content, ['Context', 'File Origin', 'Resource Type'])}
        infosTag = td(infoBlock(infos_c), 'class="titlesub log" style="width:40%"')

        success = val['success']
        if success:
            getTag = td('GET Success', 'class="pass"')
        else:
            getTag = td('GET Failure', 'class="fail"')


        countsTag = td(infoBlock(val['counts'], split='', ffunc=applyInfoSuccessColor), 'class="log"')

        rhead = ''.join([buttonTag, infosTag, getTag, countsTag])
        for x in [('tr',), ('table', 'class=titletable'), ('td', 'class=titlerow'), ('tr')]:
            rhead = wrapTag(''.join(rhead), *x)
        entry.append(rhead)

        # actual table
        rows = [(str(i.name),
            str(i.entry), str(i.expected), str(i.actual), str(i.success.value)) for i in val['messages']]
        titles = ['Property Name', 'Value', 'Expected', 'Actual', 'Result']
        widths = ['15','30','30','10','15']
        tableHeader = tableBlock(rows, titles, widths, ffunc=applySuccessColor)

        #    lets wrap table and errors and warns into one single column table
        tableHeader = tr(td((tableHeader)))

        if(printCSV):
            rsvLogger.info(','.join(infos_a))
            rsvLogger.info(','.join(infos_content))
            rsvLogger.info(','.join(titles))
            rsvLogger.info('\n'.join([','.join(x) for x in rows]))
            rsvLogger.info(',')

        # warns and errors
        errors = val['errors']
        if len(errors) == 0:
            errors = 'No errors'
        infos = errors.split('\n')
        errorTags = tr(td(infoBlock(infos), 'class="fail log"'))

        warns = val['warns']
        if len(warns) == 0:
            warns = 'No warns'
        infos = warns.split('\n')
        warnTags = tr(td(infoBlock(infos), 'class="warn log"'))

        tableHeader += errorTags
        tableHeader += warnTags
        tableHeader = table(tableHeader)
        tableHeader = td(tableHeader, 'class="results" id=\'resNum{}\''.format(cnt))

        entry.append(tableHeader)

        # append
        htmlPage += ''.join([tr(x) for x in entry])

    return wrapTag(wrapTag(htmlStrTop + wrapTag(htmlStrBodyHeader + htmlPage, 'table'), 'body'), 'html')


def writeHtml(string, path):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(string)


def htmlLogScraper(htmlReport):
    outputLogName = os.path.split(htmlReport)[-1]
    output = open('./logs/{}.csv'.format(outputLogName),'w',newline='')
    csv_output = csv.writer(output)
    csv_output.writerow(['URI','Status','Response Time','Context','File Origin','Resource Type','Property Name','Value','Expected','Actual','Result'])
    htmlLog = open(htmlReport,'r')
    soup = BeautifulSoup(htmlLog, 'html.parser')
    glanceDetails = {}
    idList = []
    table = soup.find_all('table', {'class':'titletable'})
    for tbl in table:
        tr = tbl.find('tr')
        URIresp = tr.find('td',{'class':'title'}) # URI, response time, show results button
        URI = URIresp.text.partition('(')[0]
        responseTime = URIresp.text.partition('response time')[2].split(')')[0].strip(':s')
        StatusGET = tr.find('td',{'class':'pass'}) or tr.find('td',{'class':'fail'})
        if 'Success' in StatusGET.text:
            Status = '200'
        else:
            Status = '400'

        context,FileOrigin,ResourceType = ' ',' ',' '
        if 'Context:' in tr.find_all('td')[1].text:
            context = tr.find_all('td')[1].text.split('Context:')[1].split('File')[0]
        if 'File Origin'in tr.find_all('td')[1].text:
            FileOrigin = tr.find_all('td')[1].text.split('File Origin:')[1].split('Resource')[0]
        if 'Resource Type'in tr.find_all('td')[1].text:
            ResourceType = tr.find_all('td')[1].text.split('Resource Type:')[1]
        resNumHtml = str(tr.find('div', {'class':'button warn'}))
        resNum = resNumHtml.split('.')[1].split('getElementById')[1].strip("()'")
        idList.append(resNum)
        results = URI+'*'+Status+'*'+responseTime+'*'+context+'*'+FileOrigin+'*'+ResourceType+'*' #using * for csv splitting since some values have commas
        glanceDetails[results] = resNum # mapping of results to their respective tables

    properties = soup.findAll('td',{'class':'results'})
    data = []
    for table in properties:
        tableToStr = str(table)
        tableID = tableToStr.split('id=')[1].split('>')[0].strip('"')
        if len(table.find_all('table')) == 0:
            continue
        tableBody = table.find_all('table')[-1]
        tableRows = tableBody.find_all('tr')[1:] #get rows from property tables excluding header
        for tr in tableRows:
            td = tr.find_all('td')
            row = [i.text for i in td]
            for k,v in glanceDetails.items():
                if v == tableID:
                    data.append(k+'*'.join(row))
    csv_output.writerows([x.split('*') for x in data]) #using * for csv splitting since some values have commas
    output.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Get an excel sheet of details shown in the HTML reports for the Redfish Interoperability Validator')
    parser.add_argument('htmllog' ,type=str, help = 'Path of the HTML log to be converted to csv format' )
    args = parser.parse_args()

    htmlLogScraper(args.htmllog) 

