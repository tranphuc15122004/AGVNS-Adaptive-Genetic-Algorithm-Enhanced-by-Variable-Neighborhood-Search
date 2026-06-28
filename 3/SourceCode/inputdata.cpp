#include <stdio.h>
#include <fstream>
#include <sstream>
#include <list>
#include <exception>

#include "inputdata.h"

#include "dpdp.h"


#include "rapidjson/document.h"
#include "rapidjson/filereadstream.h"

constexpr int CHARBUFFER_SIZE = 65536;

constexpr int ROUTEMAP_COLUMN_ROUTECODE = 0;
constexpr int ROUTEMAP_COLUMN_STARTID   = 1;
constexpr int ROUTEMAP_COLUMN_ENDID     = 2;
constexpr int ROUTEMAP_COLUMN_DISTANCE  = 3;
constexpr int ROUTEMAP_COLUMN_TIME      = 4;
constexpr int ROUTEMAP_COLUMN_END       = 5;

constexpr int FACTORYINFO_COLUMN_FACTORYID = 0;
constexpr int FACTORYINFO_COLUMN_LONGITUDE = 1;
constexpr int FACTORYINFO_COLUMN_LATITUDE  = 2;
constexpr int FACTORYINFO_COLUMN_PORTNUM   = 3;
constexpr int FACTORYINFO_COLUMN_END       = 4;

int InputData::readDistances( const char * filename, const bool has_header )
{
	dpdpPrintfTrace( "start reading route map...\n" );

	std::string line;

	/* open file */
	assert( filename != NULL );

	std::fstream fstr( filename );

	if( !fstr.good() )
	{
		dpdpPrintfError( "could not open file \"%s\"!\n", filename );
		return ERROR_FILE_NOTFOUND;
	}

	/* read header, if any */
	if( has_header ) {
		std::getline( fstr, line );
	}

	/* read data */
	while( std::getline( fstr, line ) )
	{
		InputMapEntity distance;

		std::stringstream lstr( line );
		std::string field;

		int field_cntr = 0;

		/* split line */
		while( std::getline( lstr, field, ',' ) )
		{
			switch( field_cntr )
			{
				case ROUTEMAP_COLUMN_ROUTECODE:
				distance.route_code = field;
				break;
				case ROUTEMAP_COLUMN_STARTID:
				distance.start_factory_id = field;
				break;
				case ROUTEMAP_COLUMN_ENDID:
				distance.end_factory_id = field;
				break;
				case ROUTEMAP_COLUMN_DISTANCE:
				distance.distance = std::stod( field );
				break;
				case ROUTEMAP_COLUMN_TIME:
				distance.time = std::stoi( field );
				break;
				case ROUTEMAP_COLUMN_END:
				default:
				dpdpPrintfError( "too many columns in Route map!\n" );
				return ERROR_FILE_PARSE;
			}

			++field_cntr;
		}

		if( field_cntr != ROUTEMAP_COLUMN_END )
		{
			dpdpPrintfError( "too few columns in Route map!\n" );
			return ERROR_FILE_PARSE;
		}

		mapentities.push_back( distance );
	}

	dpdpPrintfTrace( "reading route map has been ended\n" );
	dpdpPrintfDebug( "%zu map entity have been read\n", mapentities.size() );

	return 0;
}

int InputData::readFactories( const char * filename, const bool has_header )
{
	dpdpPrintfTrace( "start reading factory info...\n" );

	std::string line;

	/* open file */
	assert( filename != NULL );

	std::fstream fstr( filename );

	if( !fstr.good() )
	{
		dpdpPrintfError( "could not open file \"%s\"!\n", filename );
		return ERROR_FILE_NOTFOUND;
	}

	/* read header, if any */
	if( has_header ) {
		std::getline( fstr, line );
	}

	/* read data */
	while( std::getline( fstr, line ) )
	{
		InputFactory factory;

		std::stringstream lstr( line );
		std::string field;

		int field_cntr = 0;

		/* split line */
		while( std::getline( lstr, field, ',' ) )
		{
			switch( field_cntr )
			{
				case FACTORYINFO_COLUMN_FACTORYID:
				factory.id = field;
				break;
				case FACTORYINFO_COLUMN_LONGITUDE:
				factory.longitude = std::stod( field );
				break;
				case FACTORYINFO_COLUMN_LATITUDE:
				factory.latitude = std::stod( field );
				break;
				case FACTORYINFO_COLUMN_PORTNUM:
				factory.port_num = std::stoi( field );
				break;
				case FACTORYINFO_COLUMN_END:
				default:
				dpdpPrintfError( "too many columns in Factory info!\n" );
				return ERROR_FILE_PARSE;
			}

			++field_cntr;
		}

		if( field_cntr != FACTORYINFO_COLUMN_END )
		{
			dpdpPrintfError( "too few columns in Factory info!\n" );
			return ERROR_FILE_PARSE;
		}

		factories.push_back( factory );
	}

	dpdpPrintfTrace( "reading factory info has been ended\n" );
	dpdpPrintfDebug( "%zu factories have been read\n", factories.size() );

	return 0;
}

int InputData::readVehicleInfo( const char * filename )
{
	int retcode = 0;
	FILE* file = NULL;
	char* charbuffer = NULL;

	dpdpPrintfTrace( "start reading vehicle info...\n" );

	try
	{
		/* open file */
		file = fopen(filename, "rb" );

		if( NULL == file )
			throw std::runtime_error( std::string( "could not open file " ).append( filename ).c_str() );

		charbuffer = new char[CHARBUFFER_SIZE];
		rapidjson::FileReadStream frstr( file, charbuffer, CHARBUFFER_SIZE );

		dpdpPrintfTrace( "  file \"%s\" has been opened\n", filename );

		/* parse file */
		rapidjson::Document vehicle_array;
		vehicle_array.ParseStream( frstr );

		if( vehicle_array.HasParseError() )
			throw std::runtime_error( std::string( "could not parse json file! Error code: " ).append( std::to_string( vehicle_array.GetParseError() ) ).c_str() );

		dpdpPrintfTrace( "  file \"%s\" has been parsed\n", filename );

		/* process file */
		DPDP_ASSERT( vehicle_array.IsArray() );

		for( rapidjson::Value::ConstValueIterator it = vehicle_array.Begin(); it != vehicle_array.End(); ++it )
			vehicles.push_back( InputVehicle::parse( *it ) );

		dpdpPrintfTrace( "  file \"%s\" has been processed\n", filename );
	}
	catch( std::exception exc )
	{
		dpdpPrintfError( "%s\n", exc.what() );
		retcode = ERROR_FILE_PARSE;
		goto TERMINATE;
	}

	dpdpPrintfTrace( "reading vehicle info has been ended\n" );
	dpdpPrintfDebug( "%zu vehicles have been read\n", vehicles.size() );

TERMINATE:
	if( charbuffer ) delete[] charbuffer;
	return retcode;
}

int InputData::readOngingOrderItems( const char * filename )
{
	int retcode = 0;
	FILE* file = NULL;
	char* charbuffer = NULL;

	dpdpPrintfTrace( "start reading ongoing order items...\n" );

	try
	{
		/* open file */
		file = fopen(filename, "rb" );

		if( NULL == file )
			throw std::runtime_error( std::string( "could not open file " ).append( filename ).c_str() );

		charbuffer = new char[CHARBUFFER_SIZE];
		rapidjson::FileReadStream frstr( file, charbuffer, CHARBUFFER_SIZE );

		dpdpPrintfTrace( "  file \"%s\" has been opened\n", filename );

		/* parse file */
		rapidjson::Document item_array;
		item_array.ParseStream( frstr );

		if( item_array.HasParseError() )
			throw std::runtime_error( std::string( "could not parse json file! Error code: " ).append( std::to_string( item_array.GetParseError() ) ).c_str() );

		dpdpPrintfTrace( "  file \"%s\" has been parsed\n", filename );

		/* process file */
		DPDP_ASSERT( item_array.IsArray() );

		for( rapidjson::Value::ConstValueIterator it = item_array.Begin(); it != item_array.End(); ++it )
			ongoing_order_items.push_back( InputOrderItem::parse( *it ) );

		dpdpPrintfTrace( "  file \"%s\" has been processed\n", filename );
	}
	catch( std::exception exc )
	{
		dpdpPrintfError( "%s\n", exc.what() );
		retcode = ERROR_FILE_PARSE;
		goto TERMINATE;
	}

	dpdpPrintfTrace( "reading ongoing order items has been ended\n" );
	dpdpPrintfDebug( "%zu ongoing order items have been read\n", ongoing_order_items.size() );

TERMINATE:
	if( charbuffer ) delete[] charbuffer;
	return retcode;
}

int InputData::readUnallocatedOrderItems( const char * filename )
{
	int retcode = 0;
	FILE* file = NULL;
	char* charbuffer = NULL;

	dpdpPrintfTrace( "start reading unallocated order items...\n" );

	try
	{
		/* open file */
		file = fopen( filename, "rb" );

		if( NULL == file )
			throw std::runtime_error( std::string( "could not open file " ).append( filename ).c_str() );

		charbuffer = new char[CHARBUFFER_SIZE];
		rapidjson::FileReadStream frstr( file, charbuffer, CHARBUFFER_SIZE );

		dpdpPrintfTrace( "  file \"%s\" has been opened\n", filename );

		/* parse file */
		rapidjson::Document item_array;
		item_array.ParseStream( frstr );

		if( item_array.HasParseError() )
			throw std::runtime_error( std::string( "could not parse json file! Error code: " ).append( std::to_string( item_array.GetParseError() ) ).c_str() );

		dpdpPrintfTrace( "  file \"%s\" has been parsed\n", filename );

		/* process file */
		DPDP_ASSERT( item_array.IsArray() );

		for( rapidjson::Value::ConstValueIterator it = item_array.Begin(); it != item_array.End(); ++it )
			unallocated_order_items.push_back( InputOrderItem::parse( *it ) );

		dpdpPrintfTrace( "  file \"%s\" has been processed\n", filename );
	}
	catch( std::exception exc )
	{
		dpdpPrintfError( "%s\n", exc.what() );
		retcode = ERROR_FILE_PARSE;
		goto TERMINATE;
	}

	dpdpPrintfTrace( "reading unallocated order items has been ended\n" );
	dpdpPrintfDebug( "%zu unallocated order items have been read\n", unallocated_order_items.size() );

TERMINATE:
	if( charbuffer ) delete[] charbuffer;
	return retcode;
}
