#ifndef _DPDP_TIMER_H_
#define _DPDP_TIMER_H_

#include "dpdp.h"

#include <chrono>

typedef std::chrono::system_clock dpdp_clock;

class Timer
{
	bool started;                       // is timer started?
	dpdp_clock::time_point start_point; // start time
	long long seconds_limit;            // time limit in seconds

public:
	Timer() : started( false ), seconds_limit( -1 )
	{
	}

	void setTimeLimit( const long long seconds )
	{
		seconds_limit = seconds;
	}

	void start()
	{
		DPDP_ASSERT_ABORT( !started );

		start_point = dpdp_clock::now();
		started = true;
	}

	long long getElapsedSeconds() const 
	{
		DPDP_ASSERT_ABORT( started );

		auto end_point = dpdp_clock::now();
		
		return std::chrono::duration_cast<std::chrono::seconds>( end_point - start_point ).count();
	}

	bool timeLimitReached() const
	{
		DPDP_ASSERT_ABORT( started );

		return 0 <= seconds_limit && seconds_limit <= getElapsedSeconds();
	}
};

class GlobalTimer
{
private:
	Timer timer;

public:
	static GlobalTimer& getInstance()
	{
		static GlobalTimer instance;
		return instance;
	}

	void setTimeLimit( const long long seconds )
	{
		timer.setTimeLimit( seconds );
	}

	void start()
	{
		timer.start();
	}

	long long getElapsedSeconds() const
	{
		return timer.getElapsedSeconds();
	}

	bool timeLimitReached() const
	{
		return timer.timeLimitReached();
	}

private:
	GlobalTimer()
	{
	}

public:
	GlobalTimer( GlobalTimer const& ) = delete;
	void operator=( GlobalTimer const& ) = delete;
};

#endif
