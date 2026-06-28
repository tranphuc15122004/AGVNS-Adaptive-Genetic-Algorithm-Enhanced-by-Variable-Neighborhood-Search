#pragma once

template<typename T> struct ListItem
{
	ListItem<T> *prev, *next;

	T val;

	ListItem(const T & a)
		: prev(0), next(0), val(a)
	{
	}
	ListItem()
		: prev(0), next(0)
	{
	}
};

template<typename T> class List
{
	ListItem<T> *first, *last;
	int listSize;
public:
	List()
		: first(0), last(0), listSize(0)
	{
	}
	~List()
	{
		while (!empty()) pop_back();
	}
	List<T> &push_back(const T &a)
	{
		ListItem<T> *item;
		item = new ListItem<T>(a);
		if (0 == first)
			first = last = item;
		else {
			last->next = item;
			item->prev = last;
			last = item;
		}
		++listSize;
		return *this;
	}
	List<T>& pop_back()
	{
		if (0 != first) {
			if (last == first) {
				delete last;
				first = last = 0;
				listSize = 0;
			}
			else {
				last = last->prev;
				delete last->next;
				last->next = 0;
				--listSize;
			}
		}
		return *this;
	}
	inline bool empty() const
	{
		return 0 == first;
	}
	inline int size() const
	{
		return this->listSize;
	}
	class iterator
	{
		ListItem<T> *current;
		friend class List<T>;
	protected:
		iterator(const List<T> & list)
			: current(list.first)
		{
		}
	public:
		iterator(List<T> & list)
			: current(list.first)
		{
		}
		iterator& operator++()
		{
			if (current != 0)
				current = current->next;

			return *this;
		}
		bool atEnd()
		{
			return 0 == current;
		}
		friend  T& operator *(typename List<T>::iterator &it)
		{
			return it.current->val;
		}
		T* operator ->()
		{
			return &(current->val);
		}
		friend bool operator != (const typename List<T>::iterator &it1, const typename List<T>::iterator &it2)
		{
			return it1.current != it2.current;
		}

	};
	class const_iterator
	{
		const ListItem<T> *current;
		friend class List<T>;
	protected:
		const_iterator(const List<T> & list)
			: current(list.first)
		{
		}
	public:
		const_iterator()
			: current(0)
		{
		}
		const_iterator& operator++()
		{
			if (current != 0)
				current = current->next;

			return *this;
		}
		bool atEnd()
		{
			return 0 == current;
		}
		friend  const T& operator *(typename List<T>::const_iterator &it)
		{
			return it.current->val;
		}
		const T* operator ->()
		{
			return &(current->val);
		}
		friend bool operator != (const typename List<T>::const_iterator &it1, const typename List<T>::const_iterator &it2)
		{
			return it1.current != it2.current;
		}

	};

	inline const_iterator cbegin() const
	{
		return const_iterator(*this);
	}
	inline const_iterator cend() const
	{
		return const_iterator();
	}
	inline iterator begin() const
	{
		return iterator(*this);
	}
	inline iterator end() const
	{
		return iterator();
	}
};
