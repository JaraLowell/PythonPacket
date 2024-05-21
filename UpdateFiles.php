#! /usr/bin/php7.4
<?php
error_reporting(1);

// This is an example php file we run via cron
// 0 */3 * * * root /srv/UpdateFiles.php > /dev/null
// Presuming you have php installed, and have this file in /srv
// it will create news.txt, weather.txt and small beacon.txt (not currently used) in /run (usualy a ramdrive)
// these then symlinked to the /txtfiles folder so the radio can trasmit these on request.

$json = file_get_contents('https://weerlive.nl/api/json-data-10min.php?key=84f2b4a2b3&locatie=Mussel');
$obj  = json_decode($json, true);

function asciiart($d) {
    $line1 = "    .-.      "; $line2 = "     __)     "; $line3 = "    (        "; $line4 = "     `-᾿     "; $line5 = "      •      "; $line6 = "             ";
    if($d == 'zonnig') { $line1 = "             "; $line2 = "    \   /    "; $line3 = "     .-.     "; $line4 = "  - (   ) -  "; $line5 = "     `-'     "; $line6 = "    /   \    "; }
    if($d == 'helderenacht') { $line1 = "             "; $line2 = "  *   ,    . "; $line3 = "     ((  *   "; $line4 = "   .  `   .  "; $line5 = "             "; $line6 = "             "; }
    if($d == 'bliksem') { $line1 = "             "; $line2 = "    .--.     "; $line3 = "   (    ).   "; $line4 = "  (____(__)  "; $line5 = "   ' / ' '   "; $line6 = "  '  /  '    "; }
    if($d == 'regen') { $line1 = "             "; $line2 = "    .--.     "; $line3 = "   (    ).   "; $line4 = "  (____(__)  "; $line5 = "   ' ' ' '   "; $line6 = "  ' ' ' '    "; }
    if($d == 'buien') { $line1 = "             "; $line2 = "    .--.     "; $line3 = "   (    ).   "; $line4 = "  (____(__)  "; $line5 = "   '  '   '  "; $line6 = "    '  '     "; }
    if($d == 'hagel') { $line1 = "             "; $line2 = "    .--.     "; $line3 = "   (    ).   "; $line4 = "  (____(__)  "; $line5 = "   *\ *\ *\  "; $line6 = "   \* \* \*  "; }
    if($d == 'mist' || $d == 'nachtmist') { $line1 = "             "; $line2 = " _ - _ - _ - "; $line3 = "  _ - _ - _  "; $line4 = " _ - _ - _ - "; $line5 = "             "; $line6 = "             "; }
    if($d == 'sneeuw') { $line1 = "             "; $line2 = "    .--.     "; $line3 = "   (    ).   "; $line4 = "  (____(__)  "; $line5 = "   * * * *   "; $line6 = "  * * * *    "; }
    if($d == 'bewolkt' || $d == 'zwaarbewolkt' || $d == 'wolkennacht') { $line1 = "             "; $line2 = "    .--.     "; $line3 = "   (    ).   "; $line4 = "  (____(__)  "; $line5 = "             "; $line6 = "             "; }
    if($d == 'lichtbewolkt' || $d == 'halfbewolkt') { $line1 = "             "; $line2 = "   \__/      "; $line3 = " _ /  .-.    "; $line4 = "   \_(   ).  "; $line5 = "   /(___(__) "; $line6 = "             "; }
    if($d == 'halfbewolkt_regen') { $line1 = "    __       "; $line2 = " _`/  .-.    "; $line3 = "  ,\_(   ).  "; $line4 = "   /(___(__) "; $line5 = "    ' ' ' '  "; $line6 = "   ' ' ' '   "; }

    return [$line1, $line2, $line3, $line4, $line5, $line6];
}

function windRose($deg) {
    $winddir = ['Noord','Noordnoordoost','Noordoost','Oostnoordoost','Oost','Oostzuidoost','Zuidoost','Zuidzuidoost','Zuid','Zuidzuidwest','Zuidwest','Westzuidwest','West','Westnoordwest','Noordwest','Noordnoordwest','Noord'];
    return $winddir[round($deg*16/360)];
}

function dayword($daynum) {
    $dagen = ['maandag','dinsdag','woensdag','donderdag','vrijdag','zaterdag','zondag','maandag'];
    return $dagen[$daynum];
}

$stringa = "\r\n .ooO  NL0MSK  Ooo--------------------------------------------- " . substr($obj['liveweer'][0]['time'],0,10) . " --\r\n";
$stringa .= "|\r\n";
$stringa .= "| Bijgewerkt op " . dayword(date('N') - 1) . " rond " . date('H:i') . "\r\n";
$stringa .= "|\r\n";

// Niews via 112gronignen //
$stringa .= " .ooO  Het Nieuws  Ooo-------------------------------------------------------\r\n";

$str = file_get_contents('https://112groningen.nl/');
$DOM = new DOMDocument;
$DOM->loadHTML($str);

$items = $DOM->getElementsByTagName('div');
$span_list = array();
$count = 0;

for($i = 0; $i < $items->length; $i++) {
    $item = $items->item($i);
    if($item->getAttribute('class') == 'box-text text-left is-small') {
        $count++;

        $tmp =  explode('
', trim($item->nodeValue));

        $stringa .= "|\r\n| * " . wordwrap(iconv('UTF-8', 'ASCII//TRANSLIT',$tmp[1]),74,"\r\n|   ") . "\r\n";

        if($count >= 6) break;
    }
}

$stringa .= "|                                                        Bron 112groningen.nl\r\n";

$file = '/var/run/news.txt';
$write = fopen($file, 'w');
fwrite($write, $stringa, strlen($stringa));
fclose($write);

$stringa = '';

// weather //
$lines = asciiart($obj['liveweer'][0]['image']);
$stringa .= " .ooO  Het Weer .Ooo---------------------------------------------------------\r\n";
$stringa .= "| " . $lines[0] . " | Hier nu " . $obj['liveweer'][0]['samenv'] . "\r\n";
$stringa .= "| " . $lines[1] . " |\r\n";
$stringa .= "| " . $lines[2] . " | Temperatuur  : " . $obj['liveweer'][0]['temp'] . " (". $obj['liveweer'][0]['d0tmin'] . " tot " . $obj['liveweer'][0]['d0tmax'] . ") graden Celsius\r\n";
$stringa .= "| " . $lines[3] . " | Windsnelheid : " . $obj['liveweer'][0]['d0windk'] . " Beaufort\r\n";
$stringa .= "| " . $lines[4] . " | Windrichting : " . windRose($obj['liveweer'][0]['windrgr']) . "\r\n";
$stringa .= "| " . $lines[5] . " | Luchtdruk    : " . $obj['liveweer'][0]['luchtd'] . " hPa\r\n";
$stringa .= "|---------------`\r\n";
$stringa .= "| " . trim($obj['liveweer'][0]['verw']) . "\r\n";
$stringa .= "|\r\n"; //----------------------------------------------------------------------------\r\n";

// Space Weather //
$xmlstring = file_get_contents('https://www.hamqsl.com/solarxml.php');
$xml = simplexml_load_string($xmlstring, "SimpleXMLElement", LIBXML_NOCDATA);
$json = json_encode($xml);
$array = json_decode($json,TRUE);
$stringa .= " .ooO  Zon Weer .Ooo---------------------------------------------------------\r\n";
$stringa .= "| Zonstroom : " . $array['solardata']['solarflux'] . str_repeat(' ', 14 - strlen($array['solardata']['solarflux'])) . " ";
$stringa .= "| 10m Band overdag     : " . $array['solardata']['calculatedconditions']['band'][3]. "\r\n";
$stringa .= "| Zonspots  : " . $array['solardata']['sunspots'] . str_repeat(' ', 14 - strlen($array['solardata']['sunspots'])) . " ";
$stringa .= "| 10m Band in de avond : " . $array['solardata']['calculatedconditions']['band'][7] . "\r\n";
$stringa .= "| Zonwind   : " . $array['solardata']['solarwind'] . str_repeat(' ', 14 - strlen($array['solardata']['solarwind'])) . " ";
$stringa .= "| Signal Noise level   : " . $array['solardata']['signalnoise'] . "\r\n";
$stringa .= "`----------------------------------------------------------------------------\r\n";

/*
poor == slechte propagaties
fair == matig propagaties
good == goede propagaties
strong == zeer goede propagaties
*/

$file = '/var/run/weer.txt';
$write = fopen($file, 'w');
fwrite($write, $stringa, strlen($stringa));
fclose($write);

$stringa  = "\r\n" . $lines[0] . " NL0MSK\r\n" . $lines[1] . "\r\n" . $lines[2] . "\r\n" . $lines[3] . " Tmp: " . $obj['liveweer'][0]['temp'] . "C\r\n" . $lines[4] . " Wnd: " . $obj['liveweer'][0]['d0windk'] ."bf\r\n" . $lines[5] . "\r\n";

$file = '/var/run/beacon.txt';
$write = fopen($file, 'w');
fwrite($write, $stringa, strlen($stringa));
fclose($write);

// Grab a file somwhere else via ftp options...
/*
$remote_file = 'NEWS.GPI';
$ftp = ftp_connect('127.0.0.1');
$login_result = ftp_login($ftp, 'PIUpload', '');
ftp_put($ftp, $remote_file, $file, FTP_BINARY);
ftp_close($ftp);
*/
?>
