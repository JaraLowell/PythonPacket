function squareToLatLong(qth) {
    qth = qth.toUpperCase();
    a = qth.charCodeAt(0) - 65;
    b = qth.charCodeAt(1) - 65;
    c = qth.charCodeAt(2) - 48;
    d = qth.charCodeAt(3) - 48;
    e = qth.charCodeAt(4) - 65;
    f = qth.charCodeAt(5) - 65;

    var LatLng = [];
    LatLng['lon'] = (a*20) + (c*2) + ((e+0.5)/12) - 180;
    LatLng['lat']= (b*10) + d + ((f+0.5)/24) - 90;
    //console.log(LatLng['lat'],LatLng['lon']);
    return LatLng;
}

$( "#locator_klick" ).live( "change" , function() {
    qth = $('#locator_klick').val();
    if  (qth.length<6) { alert('Enter 6 character grid square!') };
});

$("#locator_klick").live('keyup', function(event){
    loc = $('#locator_klick').val().toUpperCase();
    if ( (loc.length==1) && ((loc.charCodeAt(0)<65) || (loc.charCodeAt(0)>82))) {loc = loc.substr(0,0);}
    if ( (loc.length==2) && ((loc.charCodeAt(1)<65) || (loc.charCodeAt(1)>82))) {loc = loc.substr(0,1);}
    if ( (loc.length==3) && ((loc.charCodeAt(2)<48) || (loc.charCodeAt(2)>57))) {loc = loc.substr(0,2);}
    if ( (loc.length==4) && ((loc.charCodeAt(3)<48) || (loc.charCodeAt(3)>57))) {loc = loc.substr(0,3);}
    if ( (loc.length==5) && ((loc.charCodeAt(4)<65) || (loc.charCodeAt(4)>88))) {loc = loc.substr(0,4);}
    if ( (loc.length==6) && ((loc.charCodeAt(5)<65) || (loc.charCodeAt(5)>88))) {loc = loc.substr(0,5);}
    $('#locator_klick').val(loc);
    if (loc.length==6) {
        var LatLng = squareToLatLong(loc);
        map.setView([LatLng.lat, LatLng.lon],13);
        geo = latlng2locality_country(LatLng.lat , LatLng.lon);
        locality = geo.locality;
        country = geo.country;
        $('#locality').val(locality);
        $('#country').html(country);
    }
});

function write_Maidenhead(x, y) {
    lng = x;
    lat = y;
    if (lat<-180) {lat = lat+360;}
    if (lat>180)  {lat = lat-360;}

    // compute and format longitudes
    // lng >0 is E, lng <0 is W
    var lngDir="N";
    if (lng < 0) {
        lngDir = "S";
        lng=-lng
    }

    // compute longitude in DMS degrees
		var lngDeg = Math.floor(lng);
		var lngMin = (lng - lngDeg) * 100;
		// min in DMS
		var lngMin2 = lngMin * 60 / 100;
		// seconds with 2 decimals
		var lngSec = ((lngMin2 - Math.floor(lngMin2)) * 60).toFixed(2);
		
		// formats DMS longitude in 000:00'00" format
		lngDeg = lngDeg + ''; // transforms to string
		// formats degrees to 000
		while (lngDeg.length < 3)
			lngDeg = "0" + lngDeg;
		// formats mins to 00
		lngMin=Math.floor(lngMin2)+'';
		while (lngMin.length < 2)
			lngMin = "0" + lngMin;
		// formats seconds to 01.00
		var tmp=lngSec.split(".");
		while (tmp[0].length <2)
		tmp[0]="0"+tmp[0];
		lngSec=tmp[0]+"."+tmp[1];		
		
		// compute and format latitudes in DMS
		// lat > 0 are North, lat<0 are South
        var latDir="E";
        if (lat < 0) {
		    latDir = "W";
			lat=-lat}
		// compute latitude in DMS
		// degrees
		var latDeg = Math.floor(lat);
		// mins
		var latMin = (lat - latDeg) * 100;
		var latMin2 = latMin * 60 / 100;
		// secs with 2 decimals
		//var latSec = Math.round((latMin2 - Math.floor(latMin2)) * 60);
		var latSec = ((latMin2 - Math.floor(latMin2)) * 60).toFixed(2);
		
		// formats DMS latitude in 00:00'00.00" format
		// degrees 00 format
		latDeg = latDeg + '';
		while (latDeg.length < 2)
			latDeg = "0" + latDeg;
		// mins 00 format
		latMin=Math.floor(latMin2)+'';
		while (latMin.length < 2)
			latMin= "0" + latMin;
		// secs 00.00 format
		var tmp=latSec.split(".");
		while (tmp[0].length <2)
			tmp[0]="0"+tmp[0];
			latSec=tmp[0]+"."+tmp[1];
		
		// computes and formats latitude in decimal 00.000000 format
		var latDec= (Math.round(lat * 1000000) / 1000000).toFixed(6);
		// make a string
		latDec=latDec+'';
		// split to get deg and decimals
		var tmp=latDec.split(".");
		// format degrees to 00 format
				while (tmp[0].length <2)
					tmp[0]="0"+tmp[0];
		// rebuild to 00.000000
		latDec=tmp[0]+"."+tmp[1];
		
		// computes and formats longitude in decimal 000.000000 format
		var lngDec= (Math.round(lng * 1000000) / 1000000).toFixed(6);
		lngDec=lngDec+'';
		var tmp=lngDec.split(".");
				while (tmp[0].length <3)
					tmp[0]="0"+tmp[0];
		lngDec=tmp[0]+"."+tmp[1];
		
		// construct array for return
        var LatLng = []; // create an array ( easier than new Array(4) )
		// adds signs and separators
		LatLng['latDec']= latDec + latDir;
		LatLng['lngDec']= lngDec + lngDir;
		LatLng['latDeg']= latDeg + "°" + latMin + "'" + latSec + "\""+ latDir;
		LatLng['lngDeg']= lngDeg + "°" + lngMin + "'" + lngSec + "\""+ lngDir;
   return LatLng
}

function LatLng2Loc(y, x, num) {
	if (x<-180) {x=x+360;}
	if (x>180) {x=x-360;}
	var yqth, yi, yk, ydiv, yres, ylp, y;
    var ycalc = new Array(0,0,0);
    var yn    = new Array(0,0,0,0,0,0,0);

    var ydiv_arr=new Array(10, 1, 1/24, 1/240, 1/240/24);
    ycalc[0] = (x + 180)/2;
    ycalc[1] =  y +  90;

    for (yi = 0; yi < 2; yi++) {
	for (yk = 0; yk < 5; yk++) {
	    ydiv = ydiv_arr[yk];
	    yres = ycalc[yi] / ydiv;
	    ycalc[yi] = yres;
	    if (ycalc[yi] > 0) ylp = Math.floor(yres); else ylp = Math.ceil(yres);
	    ycalc[yi] = (ycalc[yi] - ylp) * ydiv;
	    yn[2*yk + yi] = ylp;
	}
    }

    var qthloc="";
    if (num >= 2) qthloc+=String.fromCharCode(yn[0] + 0x41) + String.fromCharCode(yn[1] + 0x41);
    if (num >= 4) qthloc+=String.fromCharCode(yn[2] + 0x30) + String.fromCharCode(yn[3] + 0x30);
    if (num >= 6) qthloc+=String.fromCharCode(yn[4] + 0x41) + String.fromCharCode(yn[5] + 0x41);
    if (num >= 8) qthloc+=' ' + String.fromCharCode(yn[6] + 0x30) + String.fromCharCode(yn[7] + 0x30);
    if (num >= 10) qthloc+=String.fromCharCode(yn[8] + 0x61) + String.fromCharCode(yn[9] + 0x61);
	return qthloc;
	
}

function latlng2locality_country (lat, lng) {
	if (lng<-180) {lng = lng+360;}
	if (lng>180)  {lng = lng-360;}
	var result = null;	
	var locality = "";
	var country = "";
	
    $.ajax({
	    async: false,
        type: 'GET',
        dataType: "json",
        url: "https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat="+lat+"&lon="+lng,
        data: {},
       success: function(data){
	    if (typeof data.address.country !== 'undefined') {
         country = data.address.country;
		}
        if (typeof data.address.city !== 'undefined') {
         locality = data.address.city;
		}
		result = { country: country, locality: locality };
		},
        //error: function () { console.log('error'); } 
    }); 
return result;		
}

function geocode(addr)
{
	var result = null;	
	var lat = 0;
	var lon = 0;
	var country = "";
	
    $.ajax({
	    async: false,
        type: 'GET',
        dataType: "json",
        url: "https://nominatim.openstreetmap.org/search/"+addr+"?format=json&addressdetails=1&limit=1",
        data: {},
       success: function(data){
	    if (typeof data[0].lat !== 'undefined') {
         lat = parseFloat(data[0].lat,10);
		}
		if (typeof data[0].lon !== 'undefined') {
         lon = parseFloat(data[0].lon,10);
		}
        if (typeof data[0].address.country !== 'undefined') {
         country = data[0].address.country;
		}
		result = { country: country, lat: lat, lng:lon };
		},
        //error: function () { console.log('error'); } 
    }); 
return result;		
}	

		 
	 function onMapClick(event) {
				    var LatLng = event.latlng;
                    var lat = LatLng.lat; 
					var lng = LatLng.lng; 					
					var locator = LatLng2Loc(lat,lng, 10);
					$('#locator_klick').val(locator);
					geo = latlng2locality_country(lat , lng);
					locality = geo.locality;
					country = geo.country;
					$('#locality').val(locality);
					$('#country').html(country);
					};
					
	function onMapMove(event) {
				    var LatLng = event.latlng;
                    var lat = LatLng.lat; 
					var lng = LatLng.lng; 					
					//alert(lng);
					var LatLng2 = write_Maidenhead (lat,lng);
					$('#latDeg').html(LatLng2.latDeg);
					$('#lngDeg').html(LatLng2.lngDeg);
					$('#latDec').html(LatLng2.latDec);
					$('#lngDec').html(LatLng2.lngDec);
					var locator = LatLng2Loc(lat,lng, 10);
					$('#locator').html(locator);
					};
		 
		 $( "#locality" ).live( "change" ,function() {
			var locality = $('#locality').val();
			var geo = geocode(locality);
			var locator = LatLng2Loc(geo.lat,geo.lng, 10);
			$('#locator_klick').val(locator);
			map.setView([geo.lat, geo.lng],13);
			$('#country').html(geo.country);
		});
		
		$("#clear_button").live('click',function(){
					$('#locator_klick').val("");
					$('#locality').val("");
					$('#country').html("");
					map.setView([19, 0],2);
		 });
	
		$("#dxcluster_map_button").live('click',function(){
				document.location.href = "../map";
		 });
		 
		 $("#dxcluster_list_button").live('click',function(){
				document.location.href = "..";
		 });
	